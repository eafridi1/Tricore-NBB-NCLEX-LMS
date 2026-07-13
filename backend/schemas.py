from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v


class RegisterResponse(BaseModel):
    message: str = "Account created. Check your email to verify."
    user_id: int


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., example="sarah@example.com")
    password: str = Field(..., example="Secret123")


class LoginStep1Response(BaseModel):
    """Returned after correct password — 2FA code has been emailed."""
    status: str = "otp_sent"
    message: str = "Check your email for a 6-digit code."


class TwoFAVerifyRequest(BaseModel):
    """Step 2 of login — submit the OTP from email."""
    otp: str = Field(..., min_length=6, max_length=6, example="482910")


class TokenResponse(BaseModel):
    """Full login success. refresh_token is sent as an HttpOnly cookie, not here."""
    access_token: str
    token_type: str = "bearer"


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., example="a3f9c2...")


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., example="reset_token_hex...")
    new_password: str = Field(..., min_length=8, example="NewSecret456")


class MessageResponse(BaseModel):
    """Generic success message."""
    message: str




