"""Read-only GitHub: what is happening on the owner's projects (workflow runs, pull
requests, recent commits). Uses a fine-grained token that can only read."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

import requests

from ..clock import to_iso
from . import STR, Tool, obj

API = "https://api.github.com"
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHub:
    def __init__(self, token: str, owner: str | None = None, session: requests.Session | None = None):
        self.owner = owner
        self.http = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}

    def _repo(self, repo: str) -> str:
        repo = repo.strip().removeprefix("https://github.com/").strip("/")
        if "/" not in repo and self.owner:
            repo = f"{self.owner}/{repo}"
        if not REPO_RE.match(repo):
            raise ValueError("Repository must look like owner/name")
        return repo

    def _get(self, path: str, **params) -> dict | list:
        resp = self.http.get(f"{API}{path}", headers=self.headers, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def runs(self, repo: str, limit: int = 10) -> list[dict]:
        data = self._get(f"/repos/{self._repo(repo)}/actions/runs", per_page=limit)
        return [{"workflow": r.get("name"), "status": r.get("status"), "result": r.get("conclusion"),
                 "branch": r.get("head_branch"), "started": r.get("run_started_at") or r.get("created_at"),
                 "url": r.get("html_url")} for r in data.get("workflow_runs", [])]

    def status(self, repo: str) -> dict:
        full = self._repo(repo)
        pulls = self._get(f"/repos/{full}/pulls", state="open", per_page=10)
        commits = self._get(f"/repos/{full}/commits", per_page=5)
        return {
            "repo": full,
            "recent_runs": self.runs(full, 8),
            "open_pull_requests": [{"number": p["number"], "title": p["title"], "author": p["user"]["login"],
                                    "updated": p["updated_at"]} for p in pulls],
            "recent_commits": [{"message": c["commit"]["message"].splitlines()[0],
                                "date": c["commit"]["author"]["date"]} for c in commits],
        }

    def failures_since(self, repos: tuple[str, ...], since: datetime) -> list[dict]:
        cutoff = to_iso(since)[:19]
        out = []
        for repo in repos:
            try:
                for run in self.runs(repo, 20):
                    started = (run.get("started") or "")[:19]
                    if run.get("result") in ("failure", "timed_out") and started >= cutoff:
                        out.append({"repo": repo, **run})
            except requests.RequestException as exc:
                out.append({"repo": repo, "error": str(exc)[:200]})
        return out


def github_tools(gh: GitHub, watch: tuple[str, ...], now) -> list[Tool]:
    def project_status(repo: str) -> dict:
        return gh.status(repo)

    def recent_failures(hours: int = 24) -> dict:
        since = now() - timedelta(hours=max(1, min(hours, 24 * 14)))
        return {"watched_repos": list(watch), "failures": gh.failures_since(watch, since)}

    return [
        Tool("github_project_status",
             "Latest workflow runs, open pull requests and recent commits for one repo. "
             f"Watched repos: {', '.join(watch) or 'none set'}.",
             obj({"repo": {**STR, "description": "owner/name, or just name for the owner's repos"}}, ["repo"]),
             project_status, untrusted=True),
        Tool("github_recent_failures", "Failed workflow runs across the watched repos in the last N hours.",
             obj({"hours": {"type": "integer"}}), recent_failures, untrusted=True),
    ]
