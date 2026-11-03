from app.core.db import SessionLocal
from app.seed import DEMO_PASSWORD, seed_demo

if __name__ == "__main__":
    db = SessionLocal()
    try:
        out = seed_demo(db)
        print("Demo data:", out)
        print(f"Logins (password {DEMO_PASSWORD}): teacher@planit.kz, director@planit.kz, admin@planit.kz, student@planit.kz")
    finally:
        db.close()
