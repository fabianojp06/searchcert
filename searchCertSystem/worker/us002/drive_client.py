"""
Cliente Google Drive API v3 (somente leitura): listar filhos de pasta e baixar bytes por `file_id`.
Usado por US002, US003 e poller.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .types import DriveFileDict


FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
PDF_MIME_TYPE = "application/pdf"


@dataclass(frozen=True)
class DriveClientConfig:
    service_account_file: str
    include_shared_drives: bool = True


class DriveClient:
    def __init__(self, config: DriveClientConfig) -> None:
        self._config = config
        creds = service_account.Credentials.from_service_account_file(
            config.service_account_file,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        self._drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    def download_file_bytes(self, file_id: str) -> bytes:
        import io

        request = self._drive.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()

    def iter_children(
        self,
        parent_id: str,
        *,
        mime_type: str | None = None,
        fields: str = "nextPageToken, files(id,name,mimeType,webViewLink)",
        page_size: int = 1000,
    ) -> Iterable[DriveFileDict]:
        q = f"'{parent_id}' in parents and trashed=false"
        if mime_type:
            q += f" and mimeType='{mime_type}'"

        page_token: str | None = None
        while True:
            kwargs = {
                "q": q,
                "fields": fields,
                "pageSize": page_size,
                "pageToken": page_token,
            }

            if self._config.include_shared_drives:
                kwargs.update(
                    {
                        "supportsAllDrives": True,
                        "includeItemsFromAllDrives": True,
                        "corpora": "allDrives",
                    }
                )

            resp = self._drive.files().list(**kwargs).execute()
            for item in resp.get("files", []) or []:
                yield item  # type: ignore[misc]

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

