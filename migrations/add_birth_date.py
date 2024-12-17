from sqlalchemy import create_engine, text
from datetime import datetime, timezone

# Database connection
SQLALCHEMY_DATABASE_URL = "postgresql://qr_code_inventory_user:nbvjirF9291@192.168.122.192/qr_code_inventory_db_unit"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def migrate():
    with engine.connect() as connection:
        # First create the enum type if it doesn't exist
        connection.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = 'user_role'
                ) THEN 
                    CREATE TYPE user_role AS ENUM ('ADMIN', 'MASTER', 'ADJUSTER', 'WORKER');
                END IF;
            END $$;
        """))
        connection.commit()

        # Create users table if it doesn't exist
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                birth_date DATE NOT NULL,
                username VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role user_role NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP WITH TIME ZONE,
                otp VARCHAR,
                failed_login_attempts INTEGER DEFAULT 0,
                last_failed_login TIMESTAMP WITH TIME ZONE,
                is_locked BOOLEAN DEFAULT FALSE,
                lock_expiry TIMESTAMP WITH TIME ZONE
            );
        """))
        connection.commit()

        # Add missing columns if they don't exist
        columns_to_add = [
            ("email", "VARCHAR(255) NOT NULL UNIQUE"),
            ("full_name", "VARCHAR(255) NOT NULL"),
            ("birth_date", "DATE NOT NULL"),
            ("password_hash", "VARCHAR(255) NOT NULL"),
            ("role", "user_role NOT NULL"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
            ("created_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"),
            ("last_login_at", "TIMESTAMP WITH TIME ZONE"),
            ("otp", "VARCHAR"),
            ("failed_login_attempts", "INTEGER DEFAULT 0"),
            ("last_failed_login", "TIMESTAMP WITH TIME ZONE"),
            ("is_locked", "BOOLEAN DEFAULT FALSE"),
            ("lock_expiry", "TIMESTAMP WITH TIME ZONE")
        ]

        for column_name, column_type in columns_to_add:
            connection.execute(text(f"""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name = 'users' 
                        AND column_name = '{column_name}'
                    ) THEN 
                        ALTER TABLE users ADD COLUMN {column_name} {column_type};
                    END IF;
                END $$;
            """))
            connection.commit()

if __name__ == "__main__":
    migrate()
