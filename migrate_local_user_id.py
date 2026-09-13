import sqlite3


DATABASE = "afrisync.db"

connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()


cursor.execute("""
    PRAGMA table_info(projects)
""")

columns = [
    row[1]
    for row in cursor.fetchall()
]


if "user_id" not in columns:

    print("Adding user_id column to local database...")

    cursor.execute("""
        ALTER TABLE projects
        ADD COLUMN user_id TEXT
    """)

else:

    print("Local user_id column already exists.")


# ============================================================
# CURRENT USER ID
# ============================================================

USER_ID = "legacy-user"


cursor.execute("""
    UPDATE projects
    SET user_id = ?
    WHERE user_id IS NULL
       OR user_id = ''
""", (USER_ID,))


updated = cursor.rowcount

connection.commit()

connection.close()


print(
    f"Existing local projects assigned to user: {updated}"
)

print("Local migration completed successfully.")