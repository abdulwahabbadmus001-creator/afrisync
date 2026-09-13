import subprocess
import sys


def run_script(script):
    print()
    print("=" * 50)
    print(f"Running: {script}")
    print("=" * 50)
    print()

    subprocess.run(
        [sys.executable, script],
        check=False
    )

    print()
    input("Press ENTER to return to the main menu...")


def main():

    while True:

        print()
        print("=" * 55)
        print("                 AFRISYNC")
        print("        Offline-First Project System")
        print("=" * 55)
        print()
        print("1. Create Project")
        print("2. View Local Projects")
        print("3. Edit Project")
        print("4. Sync Local → Server")
        print("5. Pull Server → Local")
        print("6. Retry Failed Sync")
        print("7. Exit")
        print()

        choice = input("Select an option: ").strip()

        if choice == "1":
            run_script("create_project.py")

        elif choice == "2":
            run_script("view_projects.py")

        elif choice == "3":
            run_script("edit_project.py")

        elif choice == "4":
            run_script("sync.py")

        elif choice == "5":
            run_script("pull_sync.py")

        elif choice == "6":
            run_script("retry_sync.py")

        elif choice == "7":
            print()
            print("Exiting AfriSync.")
            break

        else:
            print()
            print("Invalid option. Please select 1-7.")


if __name__ == "__main__":
    main()