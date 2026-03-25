from __future__ import annotations

from searchCertSystem.worker.us002.drive_client import DriveClient


def download_pdf_bytes(drive: DriveClient, file_id: str) -> bytes:
    return drive.download_file_bytes(file_id)

