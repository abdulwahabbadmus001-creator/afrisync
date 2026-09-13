import sqlite3
import uuid


DATABASE = "server.db"


connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()


# ============================================================
# CHECK WHETHER user_id ALREADY EXISTS
# ============================================================

cursor.execute("""
    PRAGMA table_info(projects)
""")

columns = [
    row[1]
    for row in cursor.fetchall()
]


if "user_id" not in columns:

    print("Adding user_id column...")

    cursor.execute("""
        ALTER TABLE projects
        ADD COLUMN user_id TEXT
    """)

else:

    print("user_id column already exists.")


# ============================================================
# ASSIGN EXISTING PROJECTS TO LEGACY USER
# ============================================================

LEGACY_USER_ID = "legacy-user"


cursor.execute("""
    UPDATE projects
    SET user_id = ?
    WHERE user_id IS NULL
       OR user_id = ''
""", (LEGACY_USER_ID,))


updated = cursor.rowcount


connection.commit()


print(
    f"Existing projects assigned to legacy user: {updated}"
)


# ============================================================
# VERIFY
# ============================================================

cursor.execute("""
    SELECT
        id,
        project_uuid,
        user_id,
        name
    FROM projects
    ORDER BY id
""")


rows = cursor.fetchall()


print()
print("Projects after migration:")

for row in rows:
    print(row)


connection.close()

print()
print("Migration completed successfully.")