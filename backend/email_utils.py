# def send_email(to: str, subject: str, body: str):
#     print(f"\n{'='*50}\nEMAIL TO: {to}\nSUBJECT: {subject}\nBODY:\n{body}\n{'='*50}\n")

"""
backend/email_utils.py
========================
Real email via Resend API.
Console fallback when RESEND_API_KEY is not set (local dev without a key).

Why Resend over SendGrid/Mailgun:
  - Simplest API (one function, one SDK call)
  - Best free tier (3,000 emails/month)
  - Works from Pakistan without VPN or regional restrictions
  - No domain verification required for testing (use onboarding@resend.dev)
"""

import os
import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
APP_NAME   = os.getenv("APP_NAME", "Nurses Beyond Borders")


def send_email(to: str, subject: str, body: str) -> None:
    if not RESEND_API_KEY:
        # Console fallback — dev without a key, or test environment.
        # Tests never set RESEND_API_KEY so this path is always hit
        # in the test suite, which is correct: we don't want 218 tests
        # firing real email requests.
        print(f"\n📧 EMAIL (console mode — set RESEND_API_KEY for real delivery)")
        print(f"   TO:      {to}")
        print(f"   SUBJECT: {subject}")
        print(f"   BODY:\n{body}\n")
        return

    resend.api_key = RESEND_API_KEY
    resend.Emails.send({
        "from": f"{APP_NAME} <{FROM_EMAIL}>",
        "to": [to],
        "subject": subject,
        "text": body,
    })