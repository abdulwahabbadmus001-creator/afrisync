import sqlite3

connection = sqlite3.connect("afrisync.db")
cursor = connection.cursor()

cursor.execute("PRAGMA table_info(projects)")

columns = cursor.fetchall()

print("Projects table schema:")
print()

for column in columns:
    print(column)

connection.close()