"""Tests that cover only part of the spec on purpose — this is the drift being demonstrated."""

from src.auth import validate_email, issue_otp, verify_otp


def test_email_validation_accepts_valid_address():
    # maps to FR-002 in 001-user-login
    assert validate_email("a@b.com") is True


def test_email_validation_rejects_missing_at():
    # maps to FR-002 in 001-user-login
    assert validate_email("ab.com") is False


def test_otp_is_issued_and_verifiable():
    # maps to FR-001 in 009-two-factor
    code = issue_otp("a@b.com")
    assert verify_otp("a@b.com", code) is True


# 注意：以下规格条目在本测试集中没有任何锚点
#   001 / FR-001  sign in with email and password
#   001 / FR-003  lock account after 5 failed attempts
#   009 / FR-003  expire the one-time code
#   009 / FR-004  reject an already used code
