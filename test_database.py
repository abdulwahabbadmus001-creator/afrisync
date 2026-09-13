from app.database import (
    get_local_connection,
    get_server_connection
)


local = get_local_connection()

print("Local database connection successful.")

local.close()


server = get_server_connection()

print("Server database connection successful.")

server.close()