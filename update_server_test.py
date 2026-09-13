import sqlite3

PROJECT_UUID = "c4f35f59-bc36-48a4-896e-42fa081260f0"

connection = sqlite3.connect("server.db")
cursor = connection.cursor()

cursor.execute("""
    UPDATE projects
    SET progress = 75
    WHERE project_uuid = ?
""", (PROJECT_UUID,))

connection.commit()

print("Rows updated:", cursor.rowcount)

cursor.execute("""
    SELECT project_uuid, name, location, progress, sync_status
    FROM projects
    WHERE project_uuid = ?
""", (PROJECT_UUID,))

print("Server database result:")
print(cursor.fetchone())

connection.close()