"""CLI do US002: mapeia o Drive e grava JSON (`python -m searchCertSystem.worker.us002`)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .drive_client import DriveClient, DriveClientConfig
from .mapper import MapperConfig, map_drive_structure


def _as_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _print_drive_help_for_common_errors(err: Exception) -> None:
    msg = str(err)
    if "accessNotConfigured" in msg or "Google Drive API has not been used in project" in msg:
        print(
            "\nERRO: A Google Drive API está desativada (ou nunca foi usada) no projeto do Google Cloud "
            "associado a esta Service Account.\n\n"
            "Como resolver:\n"
            "- No Google Cloud Console, habilite a API: drive.googleapis.com\n"
            "- Aguarde 2–10 minutos para propagar\n"
            "- Depois rode novamente o comando.\n"
        )


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="US002 - Mapear estrutura do Google Drive (CertiBot)")
    parser.add_argument(
        "--out",
        default="output/us002.json",
        help="Caminho do arquivo JSON de saída (default: output/us002.json)",
    )
    parser.add_argument(
        "--root-folder-id",
        default=os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID"),
        help="Folder ID raiz (default: env GOOGLE_DRIVE_ROOT_FOLDER_ID)",
    )
    parser.add_argument(
        "--service-account-file",
        default=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        help="Path do JSON da Service Account (default: env GOOGLE_SERVICE_ACCOUNT_FILE)",
    )
    parser.add_argument(
        "--include-shared-drives",
        default=os.getenv("GOOGLE_DRIVE_INCLUDE_SHARED_DRIVES", "true"),
        help="Incluir Shared Drives (true/false). Default: env GOOGLE_DRIVE_INCLUDE_SHARED_DRIVES",
    )
    args = parser.parse_args()

    if not args.root_folder_id:
        raise SystemExit("Faltou --root-folder-id ou env GOOGLE_DRIVE_ROOT_FOLDER_ID.")
    if not args.service_account_file:
        raise SystemExit("Faltou --service-account-file ou env GOOGLE_SERVICE_ACCOUNT_FILE.")

    include_shared_drives = _as_bool(args.include_shared_drives, default=True)

    drive = DriveClient(
        DriveClientConfig(
            service_account_file=args.service_account_file,
            include_shared_drives=include_shared_drives,
        )
    )

    try:
        payload = map_drive_structure(drive, MapperConfig(root_folder_id=args.root_folder_id), include_links=True)
    except Exception as e:  # noqa: BLE001
        _print_drive_help_for_common_errors(e)
        raise

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK: gerado {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

