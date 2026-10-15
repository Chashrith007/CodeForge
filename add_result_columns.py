from database import get_connection

with get_connection() as connection:
    connection.execute("""
        ALTER TABLE submissions
        ADD COLUMN IF NOT EXISTS output TEXT,
        ADD COLUMN IF NOT EXISTS exit_code INTEGER;
    """)

print("Result columns are ready.")