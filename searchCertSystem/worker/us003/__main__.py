"""CLI do US003: processa `us002.json`, gera `us003.json` e opcionalmente envia ao Supabase."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from searchCertSystem.worker.us002.drive_client import DriveClient, DriveClientConfig
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


def _push_to_supabase(cfg: SupabaseConfig, us003_payload: dict) -> int:
    count = 0
    for colab in us003_payload.get("colaboradores", []) or []:
        colab_nome = colab.get("nome")
        colab_folder_id = colab.get("colaborador_folder_id")
        if not colab_nome or not colab_folder_id:
            continue

        colaborador_id = upsert_colaborador(cfg, nome=colab_nome, link_pasta=colab_folder_id)

        for cert in colab.get("certificacoes", []) or []:
            cert_nome = cert.get("nome")
            if not cert_nome:
                continue
            for pdf in cert.get("pdfs", []) or []:
                if pdf.get("status") != "ok":
                    continue
                upsert_certificacao(
                    cfg,
                    colaborador_id=colaborador_id,
                    nome_certificado=cert_nome,
                    data_emissao=pdf.get("issue_date_iso") or pdf.get("issue_date"),
                    data_validade=pdf.get("expiry_date_iso") or pdf.get("expiry_date"),
                    link_pdf=pdf.get("web_view_link") or "",
                    pdf_file_id=pdf.get("file_id"),
                    pdf_file_name=pdf.get("file_name"),
                )
                count += 1
    return count


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="US003 - Extrair datas de emissão/validade dos PDFs")
    parser.add_argument("--in", dest="in_path", default="output/us002.json", help="Entrada US002 (default: output/us002.json)")
    parser.add_argument("--out", dest="out_path", default="output/us003.json", help="Saída US003 (default: output/us003.json)")
    parser.add_argument("--max-pages", type=int, default=2, help="Máximo de páginas para extrair texto (default: 2)")
    parser.add_argument(
        "--debug-dir",
        default=None,
        help="Se definido, salva um snippet do texto extraído por PDF (ex: output/us003_debug)",
    )
    parser.add_argument(
        "--debug-text-chars",
        type=int,
        default=2000,
        help="Tamanho do snippet de texto salvo no debug (default: 2000)",
    )
    parser.add_argument(
        "--push-supabase",
        default=os.getenv("US003_PUSH_SUPABASE", "false"),
        help="Enviar para Supabase (true/false). Default: env US003_PUSH_SUPABASE",
    )
    args = parser.parse_args()

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

    in_path = Path(args.in_path)
    us002_payload = json.loads(in_path.read_text(encoding="utf-8"))

    us003_payload = process_us002_payload(
        drive,
        us002_payload,
        config=Us003Config(
            max_pages=args.max_pages if args.max_pages > 0 else None,
            debug_dir=args.debug_dir,
            debug_text_chars=args.debug_text_chars,
        ),
    )

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(us003_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: gerado {out_path}")

    if _as_bool(args.push_supabase, default=False):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise SystemExit("Para --push-supabase, configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.")
        cfg = SupabaseConfig(url=url, service_role_key=key)
        sent = _push_to_supabase(cfg, us003_payload)
        print(f"OK: enviado ao Supabase ({sent} certificações)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

