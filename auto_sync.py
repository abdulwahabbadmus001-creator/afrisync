import time

from datetime import datetime

from app.database import (
    get_local_connection
)

from app.sync_engine import (
    synchronize_pending_projects
)

from network import (
    is_server_available
)


# ============================================================
# CONFIGURATION
# ============================================================

ONLINE_CHECK_INTERVAL = 15

INITIAL_OFFLINE_RETRY = 5

MAX_OFFLINE_RETRY = 60

INITIAL_SYNC_FAILURE_RETRY = 5

MAX_SYNC_FAILURE_RETRY = 60


# ============================================================
# TIME
# ============================================================

def current_time():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# LOCAL SYNC STATE
# ============================================================

def get_sync_state(
    user_id
):
    connection = (
        get_local_connection()
    )

    cursor = connection.cursor()


    cursor.execute("""
        SELECT COUNT(*)
        FROM projects
        WHERE user_id = ?
          AND sync_status = 'PENDING'
    """, (
        user_id,
    ))

    pending = (
        cursor.fetchone()[0]
    )


    cursor.execute("""
        SELECT COUNT(*)
        FROM projects
        WHERE user_id = ?
          AND sync_status = 'CONFLICT'
    """, (
        user_id,
    ))

    conflicts = (
        cursor.fetchone()[0]
    )


    cursor.execute("""
        SELECT COUNT(*)
        FROM projects
        WHERE user_id = ?
          AND sync_status = 'SYNCED'
    """, (
        user_id,
    ))

    synced = (
        cursor.fetchone()[0]
    )


    cursor.execute("""
        SELECT COUNT(*)
        FROM projects
        WHERE user_id = ?
          AND COALESCE(is_deleted, 0) = 1
    """, (
        user_id,
    ))

    deleted = (
        cursor.fetchone()[0]
    )


    connection.close()


    return {
        "pending":
            pending,

        "conflicts":
            conflicts,

        "synced":
            synced,

        "deleted":
            deleted
    }


# ============================================================
# DISPLAY SYNC STATE
# ============================================================

def print_sync_state(
    user_id
):
    state = (
        get_sync_state(
            user_id
        )
    )


    print()

    print(
        "Local synchronization state:"
    )

    print(
        f"Pending: {state['pending']}"
    )

    print(
        f"Conflicts: {state['conflicts']}"
    )

    print(
        f"Synced: {state['synced']}"
    )

    print(
        f"Tombstones: {state['deleted']}"
    )


    return state


# ============================================================
# BACKOFF
# ============================================================

def next_backoff(
    current_delay,
    maximum
):
    return min(
        current_delay * 2,
        maximum
    )


# ============================================================
# RUN ONE AUTOMATIC SYNC
# ============================================================

def run_sync_cycle(
    user_id
):
    print()

    print(
        "========================================"
    )

    print(
        "AUTOMATIC SYNCHRONIZATION"
    )

    print(
        "========================================"
    )

    print(
        f"Time: {current_time()}"
    )

    print(
        f"User: {user_id}"
    )


    result = (
        synchronize_pending_projects(
            user_id
        )
    )


    push_failed = (
        result.get(
            "failed",
            0
        )
    )


    pull_failed = (
        result.get(
            "pull_failed",
            False
        )
    )


    state = (
        print_sync_state(
            user_id
        )
    )


    success = (
        push_failed == 0
        and
        not pull_failed
    )


    return {
        "success":
            success,

        "result":
            result,

        "state":
            state
    }


# ============================================================
# AUTOMATIC SYNCHRONIZATION WORKER
# ============================================================

def start_auto_sync(
    user_id
):
    print()

    print(
        "========================================"
    )

    print(
        "AFRISYNC BACKGROUND RECOVERY SERVICE"
    )

    print(
        "========================================"
    )

    print(
        f"User: {user_id}"
    )

    print(
        "Automatic synchronization is active."
    )

    print(
        "Press CTRL + C to stop."
    )


    was_online = None

    offline_delay = (
        INITIAL_OFFLINE_RETRY
    )

    sync_failure_delay = (
        INITIAL_SYNC_FAILURE_RETRY
    )


    while True:

        try:

            # ------------------------------------------------
            # CHECK SERVER
            # ------------------------------------------------

            online = (
                is_server_available()
            )


            # ------------------------------------------------
            # SERVER OFFLINE
            # ------------------------------------------------

            if not online:

                if (
                    was_online is not False
                ):

                    print()

                    print(
                        "========================================"
                    )

                    print(
                        "SERVER OFFLINE"
                    )

                    print(
                        "========================================"
                    )

                    print(
                        f"Detected: {current_time()}"
                    )

                    print(
                        "Local changes remain safely queued."
                    )

                    print_sync_state(
                        user_id
                    )


                print()

                print(
                    "Server unavailable."
                )

                print(
                    "Retrying connectivity in "
                    f"{offline_delay} second(s)..."
                )


                was_online = False


                time.sleep(
                    offline_delay
                )


                offline_delay = (
                    next_backoff(
                        offline_delay,
                        MAX_OFFLINE_RETRY
                    )
                )


                continue


            # ------------------------------------------------
            # CONNECTION RESTORED
            # ------------------------------------------------

            if (
                was_online is False
            ):

                print()

                print(
                    "========================================"
                )

                print(
                    "CONNECTION RESTORED"
                )

                print(
                    "========================================"
                )

                print(
                    f"Detected: {current_time()}"
                )

                print(
                    "Starting automatic recovery immediately..."
                )


            elif (
                was_online is None
            ):

                print()

                print(
                    "Server connection available."
                )


            was_online = True


            offline_delay = (
                INITIAL_OFFLINE_RETRY
            )


            # ------------------------------------------------
            # RUN BIDIRECTIONAL SYNCHRONIZATION
            # ------------------------------------------------

            cycle = (
                run_sync_cycle(
                    user_id
                )
            )


            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if cycle["success"]:

                sync_failure_delay = (
                    INITIAL_SYNC_FAILURE_RETRY
                )


                if (
                    cycle["state"][
                        "conflicts"
                    ]
                    >
                    0
                ):

                    print()

                    print(
                        "Synchronization completed, "
                        "but conflict resolution is required."
                    )

                    print(
                        "Conflicts are preserved and will "
                        "not be overwritten automatically."
                    )

                else:

                    print()

                    print(
                        "Automatic synchronization successful."
                    )


                print()

                print(
                    "Next automatic check in "
                    f"{ONLINE_CHECK_INTERVAL} second(s)..."
                )


                time.sleep(
                    ONLINE_CHECK_INTERVAL
                )


                continue


            # ------------------------------------------------
            # SYNC FAILED WHILE SERVER APPEARS ONLINE
            # ------------------------------------------------

            print()

            print(
                "Automatic synchronization was incomplete."
            )

            print(
                "Pending changes remain safely queued."
            )

            print(
                "Retrying synchronization in "
                f"{sync_failure_delay} second(s)..."
            )


            time.sleep(
                sync_failure_delay
            )


            sync_failure_delay = (
                next_backoff(
                    sync_failure_delay,
                    MAX_SYNC_FAILURE_RETRY
                )
            )


        except KeyboardInterrupt:

            print()

            print(
                "========================================"
            )

            print(
                "AFRISYNC AUTO SYNC STOPPED"
            )

            print(
                "========================================"
            )

            print(
                "No local data was deleted."
            )

            break


        except Exception as error:

            print()

            print(
                "Unexpected auto-sync error:"
            )

            print(
                error
            )

            print(
                "The recovery service will continue."
            )

            print(
                "Retrying in "
                f"{sync_failure_delay} second(s)..."
            )


            time.sleep(
                sync_failure_delay
            )


            sync_failure_delay = (
                next_backoff(
                    sync_failure_delay,
                    MAX_SYNC_FAILURE_RETRY
                )
            )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print()

    user_id = input(
        "Enter your AfriSync user ID: "
    ).strip()


    if not user_id:

        print(
            "User ID is required."
        )

    else:

        start_auto_sync(
            user_id
        )