import time

from app.sync_engine import (
    get_pending_projects,
    synchronize_pending_projects
)


MAX_RETRIES = 5

RETRY_DELAYS = [
    5,
    10,
    20,
    30,
    60
]


def retry_sync():

    print("AfriSync Retry Engine started.")

    for attempt in range(MAX_RETRIES):

        pending_projects = get_pending_projects()

        if not pending_projects:

            print()
            print("No pending projects.")
            print("All projects are synchronized.")

            return

        print()
        print(
            f"Pending projects: {len(pending_projects)}"
        )

        print(
            f"Retry attempt {attempt + 1}/{MAX_RETRIES}"
        )

        synchronize_pending_projects()

        pending_projects = get_pending_projects()

        if not pending_projects:

            print()
            print(
                "Synchronization completed successfully."
            )

            return

        if attempt < MAX_RETRIES - 1:

            delay = RETRY_DELAYS[attempt]

            print()
            print(
                "Synchronization still pending."
            )

            print(
                f"Waiting {delay} seconds before retry..."
            )

            time.sleep(delay)

    print()
    print("Maximum retry attempts reached.")

    print(
        "Pending projects remain safely in the queue."
    )


if __name__ == "__main__":
    retry_sync()