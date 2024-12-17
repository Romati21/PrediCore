from sqlalchemy import create_engine, text
from datetime import datetime, timezone

# Database connection
SQLALCHEMY_DATABASE_URL = "postgresql://qr_code_inventory_user:nbvjirF9291@192.168.122.192/qr_code_inventory_db_unit"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def migrate():
    with engine.connect() as connection:
        # Create user_sessions table if it doesn't exist
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                ip_address VARCHAR(45),
                user_agent VARCHAR(255),
                last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                access_token_jti VARCHAR(255),
                refresh_token_jti VARCHAR(255),
                expired_at TIMESTAMP WITH TIME ZONE,
                cleanup_reason VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        connection.commit()

if __name__ == "__main__":
    migrate()
