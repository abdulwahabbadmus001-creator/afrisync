import sqlite3

connection = sqlite3.connect("afrisync.db")
cursor = connection.cursor()

project_uuid = input("Enter project UUID: ").strip()

cursor.execute("""
    SELECT
        project_uuid,
        sync_status,
        last_synced_at
    FROM projects
    WHERE project_uuid = ?
""", (project_uuid,))

result = cursor.fetchone()

if result:
    print("\nDatabase result:")
    print("UUID:", result[0])
    print("Status:", result[1])
    print("Last Synced At:", result[2])
else:
    print("Project not found.")

connection.close()