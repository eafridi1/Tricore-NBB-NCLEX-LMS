"""
backend/validators.py
======================
Shared Pydantic validators used across multiple routers.
Import from here — never redefine these inline in individual router files.

Usage:
    from validators import StrongPassword
    
    class RegisterRequest(BaseModel):
        password: StrongPassword

    # In the route, extract the real value for hashing:
    hash_password(data.password.get_secret_value())
"""

import re
from typing import Annotated

from pydantic import SecretStr, AfterValidator


def _validate_password(secret: SecretStr) -> SecretStr:
    """
    Validates password strength after Pydantic has already confirmed
    the value is a non-empty string.

    Rules (matches what was communicated to users in the frontend
    password strength indicator in register/page.tsx — keep in sync):
      - 8+ characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character

    Uses SecretStr so the password value is NEVER included in:
      - repr() / str() output
      - Pydantic validation error messages
      - Log lines
      - Sentry / error tracking payloads

    NOTE: this validator runs AFTER Pydantic constructs the SecretStr,
    so the raw value is only briefly accessible via get_secret_value()
    inside this function. It is never stored on the model as a plain str.
    """
    password = secret.get_secret_value()

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")

    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")

    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'`~]', password):
        raise ValueError("Password must contain at least one special character (!@#$%^&* etc.).")

    return secret


# The reusable type — annotate any password field with this
StrongPassword = Annotated[SecretStr, AfterValidator(_validate_password)]