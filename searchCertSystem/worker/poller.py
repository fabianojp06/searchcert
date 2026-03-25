from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from searchCertSystem.worker.us002.drive_client import DriveClient, DriveClientConfig
from searchCertSystem.worker.us002.mapper import MapperConfig, map_drive_structure
from searchCertSystem.worker.us003.process_us002 import Us003Config, process_us002_payload
from searchCertSystem.worker.us003.supabase_repo import SupabaseConfig, upsert_certificacao, upsert_colaborador


def _as_bool(value: object, default: bool = False) -> bool:
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


def _load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("processed_pdf_file_ids", []) if isinstance(data, dict) else []
        return {str(x) for x in items if x}
    except Exception:  # noqa: BLE001
        return set()


def _save_checkpoint(path: Path, processed: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {"processed_pdf_file_ids": sorted(processed)}
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _filter_us002_payload_incremental(us002_payload: dict[str, Any], processed_ids: set[str]) -> dict[str, Any]:
    """
    Mantém a estrutura, mas remove PDFs cujo file_id já está no checkpoint.
    """
    out = dict(us002_payload)
    out_colabs: list[dict[str, Any]] = []
    for colab in us002_payload.get("colaboradores", []) or []:
        out_certs: list[dict[str, Any]] = []
        for cert in colab.get("certificacoes", []) or []:
            pdfs = []
            for pdf in cert.get("pdfs", []) or []:
                fid = pdf.get("file_id")
                if fid and str(fid) in processed_ids:
                    continue
                pdfs.append(pdf)
            cert2 = dict(cert)
            cert2["pdfs"] = pdfs
            out_certs.append(cert2)
        colab2 = dict(colab)
        colab2["certificacoes"] = out_certs
        out_colabs.append(colab2)
    out["colaboradores"] = out_colabs
    return out


def _run_once(
    *,
    out_us002: Path,
    out_us003: Path,
    max_pages: int | None,
    debug_dir: str | None,
    checkpoint_file: Path,
) -> tuple[int, int]:
    root_folder_id = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID")
    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    include_shared = os.getenv("GOOGLE_DRIVE_INCLUDE_SHARED_DRIVES", "true")
    if not root_folder_id:
        raise SystemExit("Faltou env GOOGLE_DRIVE_ROOT_FOLDER_ID.")
    if not sa_file:
        raise SystemExit("Faltou env GOOGLE_SERVICE_ACCOUNT_FILE.")

    drive = DriveClient(
        DriveClientConfig(
            service_account_file=sa_file,
            include_shared_drives=_as_bool(include_shared, default=True),
        )
    )

    us002_payload = map_drive_structure(drive, MapperConfig(root_folder_id=root_folder_id), include_links=True)
    out_us002.parent.mkdir(parents=True, exist_ok=True)
    out_us002.write_text(json.dumps(us002_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    processed_ids = _load_checkpoint(checkpoint_file)
    us002_for_processing = _filter_us002_payload_incremental(us002_payload, processed_ids)

    us003_payload = process_us002_payload(
        drive,
        us002_for_processing,
        config=Us003Config(max_pages=max_pages, debug_dir=debug_dir, debug_text_chars=2000),
    )
    out_us003.parent.mkdir(parents=True, exist_ok=True)
    out_us003.write_text(json.dumps(us003_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Persistência no Supabase (sempre)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("Para persistir, configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no .env.")
    sb = SupabaseConfig(url=url, service_role_key=key)

    sent = 0
    for colab in us003_payload.get("colaboradores", []) or []:
        colab_nome = colab.get("nome")
        colab_folder_id = colab.get("colaborador_folder_id")
        if not colab_nome or not colab_folder_id:
            continue
        colaborador_id = upsert_colaborador(sb, nome=colab_nome, link_pasta=colab_folder_id)
        for cert in colab.get("certificacoes", []) or []:
            cert_nome = cert.get("nome")
            if not cert_nome:
                continue
            for pdf in cert.get("pdfs", []) or []:
                if pdf.get("status") != "ok":
                    continue
                upsert_certificacao(
                    sb,
                    colaborador_id=colaborador_id,
                    nome_certificado=cert_nome,
                    data_emissao=pdf.get("issue_date_iso") or pdf.get("issue_date"),
                    data_validade=pdf.get("expiry_date_iso") or pdf.get("expiry_date"),
                    link_pdf=pdf.get("web_view_link") or "",
                    pdf_file_id=pdf.get("file_id"),
                    pdf_file_name=pdf.get("file_name"),
                )
                sent += 1
                if pdf.get("file_id"):
                    processed_ids.add(str(pdf["file_id"]))

    _save_checkpoint(checkpoint_file, processed_ids)

    return (len(us002_payload.get("colaboradores", []) or []), sent)


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Poller: US002 + US003 + persistência no Supabase (a cada N segundos)")
    parser.add_argument("--interval", type=int, default=int(os.getenv("POLL_INTERVAL_SECONDS", "300")), help="Intervalo em segundos (default: 300)")
    parser.add_argument("--once", action="store_true", help="Executa uma vez e sai (para teste).")
    parser.add_argument("--out-us002", default="output/us002.json", help="Saída US002 (default: output/us002.json)")
    parser.add_argument("--out-us003", default="output/us003.json", help="Saída US003 (default: output/us003.json)")
    parser.add_argument(
        "--checkpoint-file",
        default=os.getenv("POLL_CHECKPOINT_FILE", "output/poller_checkpoint.json"),
        help="Arquivo de checkpoint incremental (default: output/poller_checkpoint.json)",
    )
    parser.add_argument("--max-pages", type=int, default=int(os.getenv("POLL_MAX_PAGES", "3")), help="Máx páginas para extrair texto (default: 3)")
    parser.add_argument("--debug-dir", default=os.getenv("POLL_DEBUG_DIR"), help="Diretório para snippets de debug (opcional)")
    args = parser.parse_args()

    interval = max(10, int(args.interval))
    max_pages = args.max_pages if args.max_pages and args.max_pages > 0 else None
    out_us002 = Path(args.out_us002)
    out_us003 = Path(args.out_us003)
    checkpoint_file = Path(args.checkpoint_file)

    while True:
        try:
            n_colabs, sent = _run_once(
                out_us002=out_us002,
                out_us003=out_us003,
                max_pages=max_pages,
                debug_dir=args.debug_dir,
                checkpoint_file=checkpoint_file,
            )
            print(f"OK: poll concluído | colaboradores={n_colabs} | certificacoes_persistidas={sent}")
        except Exception as e:  # noqa: BLE001
            print(f"ERRO no poll: {e}")

        if args.once:
            return 0

        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())

