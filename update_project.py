import sqlite3


def update_project():

    project_uuid = input("Project UUID: ").strip()

    try:
        progress = int(input("New progress (%): ").strip())
    except ValueError:
        print("Progress must be a number.")
        return

    if progress < 0 or progress > 100:
        print("Progress must be between 0 and 100.")
        return

    connection = sqlite3.connect("afrisync.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT name, location, progress
        FROM projects
        WHERE project_uuid = ?
    """, (project_uuid,))

    project = cursor.fetchone()

    if not project:
        print("Project not found.")
        connection.close()
        return

    name, location, old_progress = project

    cursor.execute("""
        UPDATE projects
        SET
            progress = ?,
            sync_status = 'PENDING',
            last_sync_error = NULL
        WHERE project_uuid = ?
    """, (
        progress,
        project_uuid
    ))

    connection.commit()
    connection.close()

    print()
    print("Project updated successfully.")
    print("Name:", name)
    print("Location:", location)
    print("Previous progress:", old_progress)
    print("New progress:", progress)
    print("Sync status: PENDING")


if __name__ == "__main__":
    update_project()