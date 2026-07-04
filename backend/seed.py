import asyncio
from database import SessionLocal
from models import User, UserRole
from auth_utils import hash_password

async def seed():
    async with SessionLocal() as db:
        admin = User(name="Admin", email="admin@tricore.app",
                     password_hash=hash_password("Admin1234"),
                     role=UserRole.admin, is_verified=True, is_active=True)
        db.add(admin)
        await db.commit()
        print("Admin seeded: admin@tricore.app / Admin1234")

asyncio.run(seed())