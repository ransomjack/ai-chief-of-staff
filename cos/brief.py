"""The morning brief: built directly from the data (no AI call), so it is fast, cheap
and always the same shape."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .clock import fmt_local, from_iso, to_iso
from .store import Store


def _day_bounds(now: datetime, tz: str) -> tuple[datetime, datetime]:
    local = now.astimezone(ZoneInfo(tz))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def build_brief(store: Store, now: datetime, tz: str, owner: str,
                outlook=None, github=None, watch: tuple[str, ...] = ()) -> str:
    day_start, day_end = _day_bounds(now, tz)
    week_end = day_start + timedelta(days=7)
    lines = [f"Good morning {owner}. Here's {day_start.strftime('%A %d %b')}."]

    if outlook is not None:
        try:
            events = outlook.events(day_start, day_end)
            lines.append("")
            lines.append(f"*Meetings ({len(events)})*" if events else "*Meetings:* none today")
            for e in events:
                when = "all day" if e.get("all_day") else e["start"][11:16]
                lines.append(f"- {when} {e['subject']}")
        except Exception as exc:
            lines += ["", f"*Meetings:* couldn't read the calendar ({type(exc).__name__})"]

    open_tasks = store.list_tasks("open")
    overdue = [t for t in open_tasks if t.get("due") and t["due"] < to_iso(day_start)]
    today = [t for t in open_tasks if t.get("due") and to_iso(day_start) <= t["due"] < to_iso(day_end)]
    week = [t for t in open_tasks if t.get("due") and to_iso(day_end) <= t["due"] < to_iso(week_end)]
    undated = [t for t in open_tasks if not t.get("due")]

    def show(title: str, tasks: list[dict], with_date: bool = True) -> None:
        if not tasks:
            return
        lines.append("")
        lines.append(f"*{title} ({len(tasks)})*")
        for t in tasks[:10]:
            who = f" — {t['person']}" if t.get("person") else ""
            when = f" ({fmt_local(from_iso(t['due']), tz)})" if with_date and t.get("due") else ""
            lines.append(f"- {t['title']}{who}{when}")
        if len(tasks) > 10:
            lines.append(f"- …and {len(tasks) - 10} more")

    show("Overdue", overdue)
    show("Due today", today)
    show("This week", week)
    show("No date yet", undated, with_date=False)
    if not open_tasks:
        lines += ["", "No open tasks. Tell me anything you need to remember."]

    if github is not None and watch:
        fails = github.failures_since(watch, now - timedelta(hours=24))
        real = [f for f in fails if "error" not in f]
        lines.append("")
        if real:
            lines.append(f"*Failed runs, last 24h ({len(real)})*")
            for f in real[:8]:
                lines.append(f"- {f['repo'].split('/')[-1]}: {f['workflow']}")
        else:
            lines.append("*Projects:* no failed runs in the last 24h")

    lines += ["", "Reply with anything to add, or ask \"what's pending on <project>\"."]
    return "\n".join(lines)
