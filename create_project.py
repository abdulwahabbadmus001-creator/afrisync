import sqlite3
import uuid


def validate_project_name(name):
    name = name.strip()

    if not name:
        return False, "Project name cannot be empty."

    if len(name) < 3:
        return False, "Project name must contain at least 3 characters."

    if not any(char.isalpha() for char in name):
        return False, "Project name must contain at least one letter."

    return True, name


def validate_location(location):
    location = location.strip()

    if not location:
        return False, "Location cannot be empty."

    if len(location) < 2:
        return False, "Location is too short."

    return True, location


def validate_progress(progress):
    try:
        progress = int(progress)
    except ValueError:
        return False, "Progress must be a whole number."

    if progress < 0 or progress > 100:
        return False, "Progress must be between 0 and 100."

    return True, progress


def create_project():
    print("=== Create AfriSync Project ===")

    while True:
        name = input("Project name: ")
        valid, result = validate_project_name(name)

        if valid:
            name = result
            break

        print(f"Invalid project name: {result}")

    while True:
        location = input("Location: ")
        valid, result = validate_location(location)

        if valid:
            location = result
            break

        print(f"Invalid location: {result}")

    while True:
        progress = input("Progress (%): ")
        valid, result = validate_progress(progress)

        if valid:
            progress = result
            break

        print(f"Invalid progress: {result}")

    project_uuid = str(uuid.uuid4())

    connection = sqlite3.connect("afrisync.db")
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO projects (
            name,
            location,
            progress,
            sync_status,
            project_uuid,
            sync_attempts
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        name,
        location,
        progress,
        "PENDING",
        project_uuid,
        0
    ))

    connection.commit()
    connection.close()

    print()
    print("Project created successfully.")
    print(f"Project UUID: {project_uuid}")
    print("Sync status: PENDING")


if __name__ == "__main__":
    create_project()