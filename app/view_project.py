from app.project_service import get_project


project_uuid = input("Enter project UUID: ").strip()

project = get_project(project_uuid)

if project:
    print("\nProject Details")
    print("----------------------------")
    print("ID:", project[0])
    print("UUID:", project[1])
    print("Name:", project[2])
    print("Location:", project[3])
    print("Progress:", f"{project[4]}%")
    print("Sync Status:", project[5])
    print("Sync Attempts:", project[6])
    print("Last Sync Attempt:", project[7])
    print("Last Sync Error:", project[8])
    print("Last Synced At:", project[9])
else:
    print("Project not found.")