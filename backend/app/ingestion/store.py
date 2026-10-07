import os

UPLOAD_DIR = "uploads"


def resolve_upload_path(image_id: str | None) -> str | None:
    """Map an image id (the uploaded filename) to a file in uploads/."""

    if not image_id:
        return None

    path = os.path.join(UPLOAD_DIR, os.path.basename(image_id))

    return path if os.path.exists(path) else None
