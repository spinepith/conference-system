from __future__ import annotations

from conference_system.app.database import SessionLocal, init_db
from conference_system.app.seed import seed_demo_data


if __name__ == "__main__":
    init_db()
    with SessionLocal() as db:
        seed_demo_data(db)
    print("Demo data created")
