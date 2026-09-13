from app.project_service import get_project, update_project


project_uuid = input("Enter project UUID: ").strip()

project = get_project(project_uuid)

if not project:
    print("Project not found.")
    exit()


print("\nCurrent Project")
print("----------------------------")
print("Name:", project[2])
print("Location:", project[3])
print("Progress:", f"{project[4]}%")
print("Sync Status:", project[5])

print("\nEnter new values.")
print("Press ENTER to keep the current value.\n")


name = input(f"Name [{project[2]}]: ").strip()
location = input(f"Location [{project[3]}]: ").strip()
progress_input = input(
    f"Progress [{project[4]}]: "
).strip()


if not name:
    name = None

if not location:
    location = None

if progress_input:
    progress = int(progress_input)
else:
    progress = None


success = update_project(
    project_uuid,
    name=name,
    location=location,
    progress=progress
)


if success:
    print("\nProject updated successfully.")
    print("Sync status: PENDING")
else:
    print("\nProject update failed.")