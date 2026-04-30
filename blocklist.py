"""Blocklist management for patients who missed appointments.

Stored in `blocked.json` next to the app:
{
  "emails": ["..."],
  "phones": ["..."]    # digits only, normalized
}
"""

import json
import re
from pathlib import Path
from threading import Lock

BLOCKED_FILE = Path(__file__).parent / "blocked.json"
_LOCK = Lock()


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _load() -> dict:
    if not BLOCKED_FILE.exists():
        return {"emails": [], "phones": []}
    try:
        data = json.loads(BLOCKED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"emails": [], "phones": []}
    data.setdefault("emails", [])
    data.setdefault("phones", [])
    return data


def _save(data: dict) -> None:
    BLOCKED_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_blocked(email: str | None, phone: str | None) -> tuple[bool, str | None]:
    """Return (blocked, reason) where reason is 'email' or 'phone'."""
    with _LOCK:
        data = _load()
    if email:
        if _normalize_email(email) in {_normalize_email(e) for e in data["emails"]}:
            return True, "email"
    if phone:
        if _normalize_phone(phone) in {_normalize_phone(p) for p in data["phones"]}:
            return True, "phone"
    return False, None


def block(email: str | None = None, phone: str | None = None) -> dict:
    with _LOCK:
        data = _load()
        added_email = added_phone = False
        if email:
            e = _normalize_email(email)
            if e and e not in {_normalize_email(x) for x in data["emails"]}:
                data["emails"].append(e)
                added_email = True
        if phone:
            p = _normalize_phone(phone)
            if p and p not in {_normalize_phone(x) for x in data["phones"]}:
                data["phones"].append(p)
                added_phone = True
        _save(data)
        return {"added_email": added_email, "added_phone": added_phone, "blocked": data}


def unblock(email: str | None = None, phone: str | None = None) -> dict:
    with _LOCK:
        data = _load()
        removed_email = removed_phone = False
        if email:
            e = _normalize_email(email)
            new = [x for x in data["emails"] if _normalize_email(x) != e]
            removed_email = len(new) != len(data["emails"])
            data["emails"] = new
        if phone:
            p = _normalize_phone(phone)
            new = [x for x in data["phones"] if _normalize_phone(x) != p]
            removed_phone = len(new) != len(data["phones"])
            data["phones"] = new
        _save(data)
        return {"removed_email": removed_email, "removed_phone": removed_phone, "blocked": data}


def list_all() -> dict:
    with _LOCK:
        return _load()
