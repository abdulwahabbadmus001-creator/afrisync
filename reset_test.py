import sqlite3

connection = sqlite3.connect("afrisync.db")
cursor = connection.cursor()

cursor.execute("""
UPDATE projects
SET sync_status = 'PENDING'
WHERE project_uuid = ?
""", ("6f76e753-d8e7-4ca1-9bff-c71f05007f79",))

connection.commit()
connection.close()

print("Test project reset to PENDING.")