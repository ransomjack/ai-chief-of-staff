"""Tasks, follow-ups and reminders: the assistant's own list, which it may change freely."""
from __future__ import annotations

from typing import Callable

from ..clock import fmt_local, from_iso, parse_when, to_iso
from ..store import Store
from . import STR, Tool, obj


def task_tools(store: Store, now: Callable, tz: str) -> list[Tool]:
    def _due(value: str) -> str:
        return to_iso(parse_when(value, tz)) if value else ""

    def _show(task: dict) -> dict:
        out = {k: task.get(k) for k in ("id", "title", "project", "person", "notes", "status")}
        if task.get("due"):
            out["due"] = fmt_local(from_iso(task["due"]), tz)
        return out

    def add_task(title: str, project: str = "", due: str = "", person: str = "",
                 notes: str = "", remind_at: str = "") -> dict:
        task = store.add_task(title, now(), project=project, due=_due(due), person=person, notes=notes)
        result = {"saved": _show(task)}
        if remind_at:
            rem = store.add_reminder(f"{title}" + (f" ({person})" if person else ""),
                                     parse_when(remind_at, tz), task_id=task["id"])
            result["reminder"] = {"id": rem["id"], "at": fmt_local(from_iso(rem["at"]), tz)}
        return result

    def list_tasks(status: str = "open", project: str = "", due_before: str = "") -> dict:
        tasks = store.list_tasks(status=status, project=project, due_before=_due(due_before))
        return {"count": len(tasks), "tasks": [_show(t) for t in tasks[:50]]}

    def update_task(task_id: str, title: str | None = None, project: str | None = None,
                    due: str | None = None, person: str | None = None, notes: str | None = None,
                    status: str | None = None) -> dict:
        if status and status not in ("open", "done"):
            raise ValueError("status must be open or done")
        task = store.update_task(task_id, now(), title=title, project=project,
                                 due=_due(due) if due else None, person=person, notes=notes, status=status)
        if not task:
            raise ValueError(f"No task {task_id}")
        if status == "done":  # a finished task should stop nagging
            for rem in store.list_reminders("pending"):
                if rem.get("task_id") == task_id:
                    store.set_reminder_status(rem["id"], "cancelled")
        return {"updated": _show(task)}

    def set_reminder(text: str, at: str, task_id: str = "") -> dict:
        when = parse_when(at, tz)
        if when <= now():
            raise ValueError("That time is already past; ask the owner for a future time.")
        rem = store.add_reminder(text, when, task_id=task_id)
        return {"reminder": rem["id"], "at": fmt_local(when, tz), "text": rem["text"]}

    def list_reminders() -> dict:
        rems = store.list_reminders("pending")
        return {"count": len(rems), "reminders": [
            {"id": r["id"], "text": r["text"], "at": fmt_local(from_iso(r["at"]), tz)} for r in rems]}

    def cancel_reminder(reminder_id: str) -> dict:
        if not store.set_reminder_status(reminder_id, "cancelled"):
            raise ValueError(f"No reminder {reminder_id}")
        return {"cancelled": reminder_id}

    when_help = ("ISO 8601, e.g. 2026-11-05T10:00 (read as the owner's local time) "
                 "or a date 2026-11-05 (means 9 AM local).")
    return [
        Tool("add_task", "Save a task or a follow-up (something to chase with a person). "
             "Optionally set a due time and a reminder.",
             obj({"title": STR, "project": {**STR, "description": "Project or area, e.g. 'AI SOC Lab'"},
                  "due": {**STR, "description": when_help},
                  "person": {**STR, "description": "Who to follow up with, if any"},
                  "notes": STR,
                  "remind_at": {**STR, "description": "When to ping the owner. " + when_help}},
                 ["title"]), add_task),
        Tool("list_tasks", "List tasks. Use due_before to find overdue or due-soon items.",
             obj({"status": {"type": "string", "enum": ["open", "done", "all"]},
                  "project": STR, "due_before": {**STR, "description": when_help}}), list_tasks),
        Tool("update_task", "Change a task, or mark it done (status=done).",
             obj({"task_id": STR, "title": STR, "project": STR, "due": STR, "person": STR,
                  "notes": STR, "status": {"type": "string", "enum": ["open", "done"]}},
                 ["task_id"]), update_task),
        Tool("set_reminder", "Ping the owner on WhatsApp at a given time.",
             obj({"text": STR, "at": {**STR, "description": when_help}, "task_id": STR},
                 ["text", "at"]), set_reminder),
        Tool("list_reminders", "List upcoming reminders.", obj({}), list_reminders),
        Tool("cancel_reminder", "Cancel a reminder.", obj({"reminder_id": STR}, ["reminder_id"]),
             cancel_reminder),
    ]
