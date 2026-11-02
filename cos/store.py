"""The assistant's own memory: tasks, reminders, recent conversation and small bits of
state. In the cloud it lives in one Azure Table; in tests it lives in a Python dict.
Both share the same logic, so what is tested is what runs."""
from __future__ import annotations

import json
import secrets
from datetime import datetime

from .clock import to_iso

TABLE = "chiefofstaff"
HISTORY_KEEP = 20  # conversation turns kept for context


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(3)}"


def _clean(data: dict) -> dict:
    return {k: v for k, v in data.items() if k != "_rk"}


class Store:
    """Business logic over a tiny key-value interface (_put/_get/_partition/_delete)."""

    # ---- backend interface -------------------------------------------------------
    def _put(self, pk: str, rk: str, data: dict) -> None: raise NotImplementedError
    def _get(self, pk: str, rk: str) -> dict | None: raise NotImplementedError
    def _partition(self, pk: str) -> list[dict]: raise NotImplementedError
    def _delete(self, pk: str, rk: str) -> None: raise NotImplementedError

    # ---- tasks and follow-ups -------------------------------------------------------
    def add_task(self, title: str, now: datetime, project: str = "", due: str = "",
                 person: str = "", notes: str = "") -> dict:
        task = {"id": new_id("t"), "title": title.strip(), "project": project.strip(),
                "due": due, "person": person.strip(), "notes": notes.strip(),
                "status": "open", "created": to_iso(now), "done_at": ""}
        self._put("task", task["id"], task)
        return task

    def get_task(self, task_id: str) -> dict | None:
        return self._get("task", task_id)

    def update_task(self, task_id: str, now: datetime, **fields) -> dict | None:
        task = self.get_task(task_id)
        if not task:
            return None
        allowed = {"title", "project", "due", "person", "notes", "status"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                task[k] = v
        if fields.get("status") == "done" and not task.get("done_at"):
            task["done_at"] = to_iso(now)
        self._put("task", task_id, task)
        return task

    def list_tasks(self, status: str = "open", project: str = "", due_before: str = "") -> list[dict]:
        tasks = self._partition("task")
        if status in ("open", "done"):
            tasks = [t for t in tasks if t.get("status") == status]
        if project:
            p = project.lower()
            tasks = [t for t in tasks if p in (t.get("project") or "").lower()]
        if due_before:
            tasks = [t for t in tasks if t.get("due") and t["due"] <= due_before]
        return sorted(tasks, key=lambda t: (t.get("due") or "9999", t.get("created", "")))

    # ---- reminders ------------------------------------------------------------------
    def add_reminder(self, text: str, at: datetime, task_id: str = "") -> dict:
        rem = {"id": new_id("r"), "text": text.strip(), "at": to_iso(at),
               "task_id": task_id, "status": "pending", "attempts": 0}
        self._put("reminder", rem["id"], rem)
        return rem

    def list_reminders(self, status: str = "pending") -> list[dict]:
        rems = [r for r in self._partition("reminder") if status == "all" or r.get("status") == status]
        return sorted(rems, key=lambda r: r["at"])

    def due_reminders(self, now: datetime) -> list[dict]:
        cutoff = to_iso(now)
        return [r for r in self.list_reminders("pending") if r["at"] <= cutoff]

    def set_reminder_status(self, rem_id: str, status: str, attempts: int | None = None) -> dict | None:
        rem = self._get("reminder", rem_id)
        if not rem:
            return None
        rem["status"] = status
        if attempts is not None:
            rem["attempts"] = attempts
        self._put("reminder", rem_id, rem)
        return rem

    # ---- conversation memory -------------------------------------------------------------
    def append_turn(self, now: datetime, user: str, assistant: str) -> None:
        rk = to_iso(now) + "-" + secrets.token_hex(2)
        self._put("history", rk, {"user": user[:4000], "assistant": assistant[:4000]})
        rows = sorted(self._partition("history"), key=lambda r: r["_rk"])
        for old in rows[:-HISTORY_KEEP]:
            self._delete("history", old["_rk"])

    def recent_turns(self, limit: int = HISTORY_KEEP) -> list[dict]:
        rows = sorted(self._partition("history"), key=lambda r: r["_rk"])
        return rows[-limit:]

    def clear_history(self) -> None:
        for row in self._partition("history"):
            self._delete("history", row["_rk"])

    # ---- small state ---------------------------------------------------------------------
    def get_state(self, key: str) -> str | None:
        row = self._get("state", key)
        return row.get("value") if row else None

    def set_state(self, key: str, value: str) -> None:
        self._put("state", key, {"value": value})

    def seen(self, message_id: str) -> bool:
        """True if this WhatsApp message was already handled (Meta can deliver twice)."""
        if self._get("seen", message_id):
            return True
        self._put("seen", message_id, {"value": "1"})
        return False


class MemoryStore(Store):
    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}

    def _put(self, pk, rk, data):
        self.rows[(pk, rk)] = json.loads(json.dumps(_clean(data)))

    def _get(self, pk, rk):
        row = self.rows.get((pk, rk))
        return dict(row, _rk=rk) if row is not None else None

    def _partition(self, pk):
        return [dict(v, _rk=rk) for (p, rk), v in self.rows.items() if p == pk]

    def _delete(self, pk, rk):
        self.rows.pop((pk, rk), None)


class TableStore(Store):
    """Azure Table Storage. Each row keeps its fields as one JSON column, so the schema
    can grow without migrations."""

    def __init__(self, connection_string: str, table: str = TABLE):
        from azure.data.tables import TableServiceClient  # imported here so tests need no Azure

        service = TableServiceClient.from_connection_string(connection_string)
        self.table = service.create_table_if_not_exists(table)

    def _put(self, pk, rk, data):
        self.table.upsert_entity({"PartitionKey": pk, "RowKey": rk, "data": json.dumps(_clean(data))})

    def _get(self, pk, rk):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            entity = self.table.get_entity(pk, rk)
        except ResourceNotFoundError:
            return None
        return dict(json.loads(entity["data"]), _rk=rk)

    def _partition(self, pk):
        rows = self.table.query_entities("PartitionKey eq @pk", parameters={"pk": pk})
        return [dict(json.loads(e["data"]), _rk=e["RowKey"]) for e in rows]

    def _delete(self, pk, rk):
        self.table.delete_entity(pk, rk)
