import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_DOC_MIME_PREFIX = "application/vnd.google-apps."
EXPORT_MIME_MAP = {
    "application/vnd.google-apps.document": (
        "application/pdf",
        ".pdf",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": (
        "image/png",
        ".png",
    ),
}


def get_drive_service(creds):
    return build("drive", "v3", credentials=creds)


def list_folder(service, folder_id="root"):
    files = []
    page_token = None

    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, size)",
            orderBy="folder,name",
            pageSize=1000,
            pageToken=page_token,
        ).execute()

        files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            return files

def escape_drive_query(value):
    return value.replace("\\", "\\\\").replace("'", "\\'")

def search_drive(service, query_text, max_results=500):
    query_text = query_text.strip()
    if not query_text:
        return []

    safe_query = escape_drive_query(query_text)

    files = []
    page_token = None

    while True:
        results = service.files().list(
            q=f"name contains '{safe_query}' and trashed=false",
            fields="nextPageToken, files(id,name,mimeType,parents,size)",
            orderBy="folder,name",
            pageSize=100,
            pageToken=page_token,
        ).execute()

        files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")

        if not page_token or len(files) >= max_results:
            return files[:max_results]


def safe_filename(name):
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip()


def format_bytes(num_bytes):
    if num_bytes is None:
        return "0 B"

    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def _folder_size_bytes(service, folder_id, cancel_check=None):
    """Recursively sums the byte size of everything inside a folder.

    Returns (total_bytes, unsized_count) where unsized_count is how many
    items (typically Google-native Docs/Sheets/Slides) had no size to report.
    """
    total = 0
    unsized = 0

    for item in list_folder(service, folder_id):
        if cancel_check and cancel_check():
            return total, unsized

        if item["mimeType"] == FOLDER_MIME:
            child_total, child_unsized = _folder_size_bytes(service, item["id"], cancel_check)
            total += child_total
            unsized += child_unsized
        else:
            size = item.get("size")
            if size is not None:
                total += int(size)
            else:
                unsized += 1

    return total, unsized


def estimate_selection_size(service, items, cancel_check=None):
    """Estimates the total download size of a mixed file/folder selection.

    Returns a dict: {"bytes": int, "unsized": int, "cancelled": bool}
    "unsized" counts items with no reportable size (Google-native docs).
    """
    total = 0
    unsized = 0

    for item in items:
        if cancel_check and cancel_check():
            return {"bytes": total, "unsized": unsized, "cancelled": True}

        if item["mimeType"] == FOLDER_MIME:
            folder_total, folder_unsized = _folder_size_bytes(service, item["id"], cancel_check)
            total += folder_total
            unsized += folder_unsized
        else:
            size = item.get("size")
            if size is not None:
                total += int(size)
            else:
                unsized += 1

    return {"bytes": total, "unsized": unsized, "cancelled": False}


def unique_path(path):
    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    counter = 1

    while True:
        candidate = f"{base} ({counter}){ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def download_file(
    service,
    file_id,
    file_name,
    output_folder,
    mime_type=None,
    progress_callback=None,
    conflict_mode="rename",
    cancel_check=None,
):
    os.makedirs(output_folder, exist_ok=True)
    clean_name = safe_filename(file_name)

    if mime_type and mime_type.startswith(GOOGLE_DOC_MIME_PREFIX):
        export_mime, ext = EXPORT_MIME_MAP.get(mime_type, ("application/pdf", ".pdf"))
        if not clean_name.lower().endswith(ext):
            clean_name += ext
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    else:
        request = service.files().get_media(fileId=file_id)

    file_path = os.path.join(output_folder, clean_name)

    if os.path.exists(file_path):
        if conflict_mode == "skip":
            return {"status": "skipped", "path": file_path, "name": clean_name}
        elif conflict_mode == "rename":
            file_path = unique_path(file_path)
        elif conflict_mode == "overwrite":
            pass
        else:
            raise ValueError(f"Unknown conflict_mode: {conflict_mode}")

    with open(file_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False

        while not done:
            if cancel_check and cancel_check():
                fh.close()
                if os.path.exists(file_path):
                    os.remove(file_path)
                return {"status": "cancelled", "path": file_path, "name": clean_name}

            status, done = downloader.next_chunk()
            if status and progress_callback:
                progress_callback(file_name, int(status.progress() * 100))

    return {"status": "downloaded", "path": file_path, "name": clean_name}


def download_folder_recursive(
    service,
    folder_id,
    folder_name,
    output_folder,
    progress_callback=None,
    conflict_mode="rename",
    cancel_check=None,
):
    local_folder = os.path.join(output_folder, safe_filename(folder_name))
    os.makedirs(local_folder, exist_ok=True)

    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "errors": []}

    items = list_folder(service, folder_id)

    for item in items:
        if cancel_check and cancel_check():
            break

        try:
            if item["mimeType"] == FOLDER_MIME:
                child_stats = download_folder_recursive(
                    service,
                    item["id"],
                    item["name"],
                    local_folder,
                    progress_callback,
                    conflict_mode,
                    cancel_check,
                )
                stats["downloaded"] += child_stats["downloaded"]
                stats["skipped"] += child_stats["skipped"]
                stats["failed"] += child_stats["failed"]
                stats["errors"].extend(child_stats["errors"])
            else:
                result = download_file(
                    service,
                    item["id"],
                    item["name"],
                    local_folder,
                    item.get("mimeType"),
                    progress_callback,
                    conflict_mode,
                    cancel_check,
                )

                if result["status"] == "downloaded":
                    stats["downloaded"] += 1
                elif result["status"] == "skipped":
                    stats["skipped"] += 1
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"{item['name']}: {e}")

    return stats