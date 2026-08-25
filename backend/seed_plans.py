"""
Seed placeholder subscription plans (idempotent — safe to re-run).
Deactivates leftover 'Checkout Test Plan' junk rows.

NOTE: prices/durations are PLACEHOLDERS pending real values from the client.
Update here (or via PATCH /subscriptions/plans) once confirmed, then re-run.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select, update

from database import SessionLocal
from models import Plan

PLACEHOLDER_PLANS = [
    {"name": "1-Month Access", "price_cents": 2999, "currency": "USD", "duration_days": 30,
     "description": "Full access for 30 days."},
    {"name": "3-Month Access", "price_cents": 6999, "currency": "USD", "duration_days": 90,
     "description": "Full access for 90 days — best for a focused study block."},
    {"name": "6-Month Access", "price_cents": 11999, "currency": "USD", "duration_days": 180,
     "description": "Full access for 180 days — best value."},
]


async def main():
    async with SessionLocal() as db:
        # 1. Deactivate leftover test/junk plans.
        await db.execute(
            update(Plan)
            .where(Plan.name == "Checkout Test Plan")
            .values(is_active=False)
        )

        # 2. Insert placeholder plans that don't already exist (idempotent by name).
        for spec in PLACEHOLDER_PLANS:
            existing = await db.scalar(
                select(Plan).where(Plan.name == spec["name"])
            )
            if existing is None:
                db.add(Plan(**spec, is_active=True))
                print(f"  + created: {spec['name']}")
            else:
                print(f"  = exists, skipped: {spec['name']}")

        await db.commit()
        print("Done. Placeholder plans seeded; junk plans deactivated.")


if __name__ == "__main__":
    asyncio.run(main())