"""
backend/email_utils.py
========================
Real email via the Resend API, with a console fallback when
RESEND_API_KEY is not set (local dev without a key, and the test suite).

Why Resend: simplest API (one SDK call), generous free tier, and it works
from Pakistan without regional restrictions or domain verification for testing.

Signature is unchanged from the original console stub — send_email(to, subject, body)
— so every existing call site in auth.py works without modification.
"""

import os

import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
APP_NAME = os.getenv("APP_NAME", "Nurses Beyond Borders")


def send_email(to: str, subject: str, body: str) -> None:
    if not RESEND_API_KEY:
        # Console fallback: local dev without a key, and the test suite
        # (tests never set RESEND_API_KEY, so they always hit this path —
        # we don't want the suite firing real network requests).
        print(f"\n{'='*50}\nEMAIL TO: {to}\nSUBJECT: {subject}\nBODY:\n{body}\n{'='*50}\n")
        return

    resend.api_key = RESEND_API_KEY
    resend.Emails.send(
        {
            "from": f"{APP_NAME} <{FROM_EMAIL}>",
            "to": [to],
            "subject": subject,
            "text": body,
        }
    )