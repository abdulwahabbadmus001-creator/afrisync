from dataclasses import dataclass
from typing import Optional


@dataclass
class Project:
    project_uuid: str
    name: str
    location: str
    progress: int
    sync_status: str = "PENDING"
    sync_attempts: int = 0
    last_sync_attempt: Optional[str] = None
    last_sync_error: Optional[str] = None