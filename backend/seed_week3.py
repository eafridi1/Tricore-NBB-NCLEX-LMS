"""Seed data for Week 3 — run after seed.py (which seeds admin user)."""
import asyncio
from datetime import datetime, timezone
from database import SessionLocal
from models import (
    Video, PDF, Announcement, Plan, Subscription, SubStatus, User
)

async def seed():
    async with SessionLocal() as db:
        # Admin user is id=1 from seed.py
        admin_id = 1

        # Plans
        plans = [
            Plan(name="1-Month Access", price_cents=2999, currency="USD",
                 duration_days=30, description="Full access for 30 days.", is_active=True),
            Plan(name="3-Month Access", price_cents=6999, currency="USD",
                 duration_days=90, description="Best value.", is_active=True),
        ]
        for p in plans:
            db.add(p)
        await db.flush()
        plan_1m = plans[0]

        # Give admin user an active subscription so they can test gated endpoints
        db.add(Subscription(
            user_id=admin_id, plan_id=plan_1m.id, status=SubStatus.active,
            start_date=datetime.now(timezone.utc),
            end_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        ))

        # Announcements (2 published, 1 draft)
        db.add(Announcement(title="Welcome to TriCore LMS",
            body="Platform is live. Start practicing today!",
            is_published=True, published_at=datetime.now(timezone.utc),
            created_by=admin_id))
        db.add(Announcement(title="New questions added",
            body="50 new Pharmacology questions are now available.",
            is_published=True, published_at=datetime.now(timezone.utc),
            created_by=admin_id))
        db.add(Announcement(title="Upcoming maintenance",
            body="Scheduled maintenance this weekend.",
            is_published=False, created_by=admin_id))

        # Videos (3, pointing at placeholder keys)
        for i, (title, cat_id) in enumerate([
            ("Cardiovascular Assessment", 1),
            ("Pharmacology Fundamentals", 2),
            ("Pediatric Nursing Overview", 3),
        ]):
            db.add(Video(title=title, category_id=cat_id,
                         storage_url=f"videos/sample-{i+1}.mp4",
                         duration_secs=1800, sort_order=i, is_published=True))

        # PDFs (2)
        db.add(PDF(title="Cardiovascular Notes", category_id=1,
                   storage_url="pdfs/cardio-notes.pdf", is_published=True))
        db.add(PDF(title="Pharmacology Quick Reference", category_id=2,
                   storage_url="pdfs/pharm-reference.pdf", is_published=True))

        await db.commit()
        print("Week 3 seed data inserted.")

asyncio.run(seed())