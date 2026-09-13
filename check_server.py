import sqlite3

connection = sqlite3.connect("server.db")
cursor = connection.cursor()

cursor.execute("SELECT COUNT(*) FROM projects")
count = cursor.fetchone()[0]

print("Projects in server database:", count)

cursor.execute("""
SELECT id, project_uuid, name, location, progress, sync_status
FROM projects
""")

projects = cursor.fetchall()

for project in projects:
    print(project)

connection.close()