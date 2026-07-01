import asyncio
from database import SessionLocal
from models import Category

CATEGORIES = [
    "Cardiovascular",
    "Pharmacology",
    "Pediatric nursing",
    "Maternal health",
    "Mental health",
    "Respiratory",
    "Endocrine",
    "Neurological",
    "Safe and effective care",
    "Health promotion",
]

async def seed():
    async with SessionLocal() as db:
        for i, name in enumerate(CATEGORIES):
            db.add(Category(name=name, sort_order=i))
        await db.commit()
        print(f"Seeded {len(CATEGORIES)} categories.")

asyncio.run(seed())