from database import get_connection

with get_connection() as connection:
    cursor = connection.execute("SELECT COUNT(*) AS total FROM submissions")
    result = cursor.fetchone()
    print(result)
