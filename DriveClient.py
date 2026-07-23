import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_DOC_MIME_PREFIX = "application/vnd.google-apps."
EXPORT_MIME_MAP = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}


def get_drive_service(creds):
    return build("drive", "v3", credentials=creds)


def list_folder(service, folder_id="root"):
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType)",
        orderBy="folder,name"
    ).execute()
    return results.get("files", [])


def safe_filename(name):
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip()


def download_file(service, file_id, file_name, output_folder, mime_type=None, progress_callback=None):
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
    with open(file_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status and progress_callback:
                progress_callback(file_name, int(status.progress() * 100))

    return file_path


def download_folder_recursive(service, folder_id, folder_name, output_folder, progress_callback=None):
    local_folder = os.path.join(output_folder, safe_filename(folder_name))
    os.makedirs(local_folder, exist_ok=True)

    items = list_folder(service, folder_id)
    for item in items:
        if item["mimeType"] == FOLDER_MIME:
            download_folder_recursive(service, item["id"], item["name"], local_folder, progress_callback)
        else:
            download_file(service, item["id"], item["name"], local_folder, item.get("mimeType"), progress_callback)