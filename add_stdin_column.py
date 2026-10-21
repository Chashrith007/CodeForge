from database import get_connection

with get_connection() as connection:
    connection.execute("""
        ALTER TABLE submissions
        ADD COLUMN IF NOT EXISTS stdin TEXT NOT NULL DEFAULT '';
    """)

print("Program input column is ready.")