import sqlite3


connection = sqlite3.connect("afrisync.db")
cursor = connection.cursor()


cursor.execute("""
    SELECT
        id,
        project_uuid,
        name,
        location,
        progress,
        sync_status,
        sync_attempts,
        last_sync_attempt,
        last_sync_error,
        last_synced_at
    FROM projects
""")

projects = cursor.fetchall()


for project in projects:
    print(project)


connection.close()