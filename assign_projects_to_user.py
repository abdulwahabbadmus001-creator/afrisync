import sqlite3


DATABASE = "server.db"

USER_ID = "9936a4c4-354a-4742-85ec-62322ef03f41"


connection = sqlite3.connect(
    DATABASE
)

cursor = connection.cursor()


cursor.execute("""
    UPDATE projects
    SET user_id = ?
    WHERE user_id = 'legacy-user'
""", (
    USER_ID,
))


updated = cursor.rowcount

connection.commit()


print(
    f"Server projects assigned to wahab: {updated}"
)


cursor.execute("""
    SELECT
        id,
        project_uuid,
        user_id,
        name,
        location,
        progress
    FROM projects
    WHERE user_id = ?
""", (
    USER_ID,
))


rows = cursor.fetchall()


print()
print("Projects belonging to wahab:")

for row in rows:
    print(row)


connection.close()