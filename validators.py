import re


def validate_project_name(name):
    """
    Validate a project name.

    Requirements:
    - Must not be empty
    - Minimum 3 characters
    - Must contain at least one letter
    - Cannot be purely numeric
    """

    if not isinstance(name, str):
        return False, "Project name must be text."

    name = name.strip()

    if not name:
        return False, "Project name cannot be empty."

    if len(name) < 3:
        return False, "Project name must contain at least 3 characters."

    if not re.search(r"[A-Za-z]", name):
        return False, "Project name must contain letters."

    return True, name


def validate_location(location):
    """
    Validate project location.

    Location must contain alphabetic words.
    Numbers-only locations are rejected.

    Examples accepted:
        Lagos State
        Ogun State
        Abuja
        Lagos-Ibadan
        St. John's

    Examples rejected:
        123
        4567
        12
    """

    if not isinstance(location, str):
        return False, "Location must be text."

    location = location.strip()

    if not location:
        return False, "Location cannot be empty."

    if len(location) < 2:
        return False, "Location is too short."

    if not re.search(r"[A-Za-z]", location):
        return False, "Location must contain words and cannot be numbers only."

    return True, location


def validate_progress(progress):
    """
    Validate project progress.
    """

    try:
        progress = int(progress)
    except (ValueError, TypeError):
        return False, "Progress must be a whole number."

    if progress < 0 or progress > 100:
        return False, "Progress must be between 0 and 100."

    return True, progress