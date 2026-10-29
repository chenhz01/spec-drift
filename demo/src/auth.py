"""Minimal auth implementation used only to demonstrate spec drift detection."""

import re
import time

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")
FAILED = {}
LOCKED = {}


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def sign_in(email: str, password: str) -> dict:
    """FR-001 (001): sign in with email and password."""
    if not validate_email(email):
        return {"ok": False, "error": "validation"}
    if LOCKED.get(email, 0) > time.time():
        return {"ok": False, "error": "locked"}
    if not _check_password(email, password):
        FAILED[email] = FAILED.get(email, 0) + 1
        if FAILED[email] >= 5:
            LOCKED[email] = time.time() + 900
        return {"ok": False, "error": "auth"}
    if two_factor_enabled(email):
        code = issue_otp(email)
        return {"ok": False, "error": "otp_required", "code": code}
    return {"ok": True, "session": _new_session(email)}


def _check_password(email: str, password: str) -> bool:
    return bool(password) and password == "correct-horse"


def _new_session(email: str) -> str:
    return f"session-{email}"


# --- 2FA ---
OTP_STORE = {}
USED = set()


def two_factor_enabled(email: str) -> bool:
    return True


def issue_otp(email: str) -> str:
    code = "123456"
    OTP_STORE[email] = (code, time.time())
    return code


def verify_otp(email: str, code: str) -> bool:
    rec = OTP_STORE.get(email)
    if not rec:
        return False
    stored, ts = rec
    if code in USED:
        return False
    if code != stored:
        return False
    if time.time() - ts > 300:
        return False
    USED.add(code)
    return True
