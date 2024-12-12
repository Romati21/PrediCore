from app.database import SessionLocal
from app.services.cleanup_service import cleanup_service

def main():
    with SessionLocal() as db:
        deactivated, deleted = cleanup_service.cleanup_all_old_sessions(db)
        print(f"Deactivated sessions: {deactivated}")
        print(f"Deleted sessions: {deleted}")

if __name__ == "__main__":
    main()
