#!/usr/bin/env python3
"""Parse one PDF locally and validate its structural output before reporting it."""
from __future__ import annotations

import argparse
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--device", choices=["cpu", "mps"], default="cpu")
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--thread-policy", choices=["legacy", "bounded"], default="bounded")
    parser.add_argument("--parse-method", choices=["auto", "ocr", "txt"], default="auto")
    args = parser.parse_args()
    if not args.name.replace("_", "").replace("-", "").isalnum():
        parser.error("Run name may contain letters, digits, hyphens and underscores")
    source = args.pdf.resolve(strict=True)
    run = ROOT / "runs" / args.name
    run.mkdir(exist_ok=False)
    record = {
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "backend": "pipeline", "device": args.device, "ocr_profile": "ch_lite",
        "formula_enabled": True, "table_enabled": True, "state": "running",
        "scientific_quality_review": "pending", "blocked_network_attempts": [],
        "threads_requested": args.threads, "thread_policy": args.thread_policy,
        "parse_method": args.parse_method,
    }
    started = time.monotonic()
    status = run / "result.json"

    def save() -> None:
        temp = status.with_suffix(".tmp")
        temp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        temp.replace(status)

    save()
    local_env = {
        "MINERU_TOOLS_CONFIG_JSON": str(ROOT / "mineru.local.json"),
        "MINERU_MODEL_SOURCE": "local", "MINERU_DEVICE_MODE": args.device,
        "MINERU_VIRTUAL_VRAM_SIZE": "1",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        "HF_HOME": str(ROOT / "cache/huggingface"),
        "MPLCONFIGDIR": str(ROOT / "cache/matplotlib"),
        "YOLO_CONFIG_DIR": str(ROOT / "cache/ultralytics"),
        "OMP_NUM_THREADS": str(args.threads), "OPENBLAS_NUM_THREADS": str(args.threads),
        "VECLIB_MAXIMUM_THREADS": str(args.threads), "MKL_NUM_THREADS": str(args.threads),
        "TOKENIZERS_PARALLELISM": "false",
    }
    os.environ.update(local_env)

    def offline_guard(event, audit_args):
        if event == "socket.connect":
            record["blocked_network_attempts"].append(str(audit_args[1]))
            # Libraries may probe connectivity at import time. A network-style
            # error lets those probes correctly select their offline path.
            raise OSError(errno.ENETUNREACH,
                          "Network connections are disabled during this local conversion")

    sys.addaudithook(offline_guard)
    try:
        import torch
        import cv2
        from pypdf import PdfReader
        from mineru.cli.common import do_parse

        if args.thread_policy == "bounded":
            from runtime_threads import configure_threads
            record["thread_configuration"] = configure_threads(args.threads)
        torch.set_num_threads(args.threads)
        torch.set_num_interop_threads(1)
        cv2.setNumThreads(1)
        expected_pages = len(PdfReader(source).pages)
        record["input_pages"] = expected_pages
        save()
        do_parse(str(run / "raw"), [source.stem], [source.read_bytes()], ["ch_lite"],
                 backend="pipeline", parse_method=args.parse_method, p_formula_enable=True,
                 p_table_enable=True, f_make_md_mode="mm_markdown")
        record["torch_threads_after_parse"] = torch.get_num_threads()
        md_files = list((run / "raw").rglob("*.md"))
        middle_files = list((run / "raw").rglob("*_middle.json"))
        if len(md_files) != 1 or len(middle_files) != 1:
            raise RuntimeError("Expected exactly one Markdown and one middle JSON output")
        md = md_files[0]
        text = md.read_text(encoding="utf-8")
        middle = json.loads(middle_files[0].read_text())
        parsed_pages = len(middle.get("pdf_info", []))
        links = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
        broken = [link for link in links if not (md.parent / link.strip("<>")).is_file()]
        record.update(markdown=str(md), markdown_characters=len(text),
                      parsed_pages=parsed_pages, image_links=len(links),
                      broken_image_links=broken, html_tables=text.count("<table"))
        if not text.strip() or parsed_pages != expected_pages or broken:
            raise RuntimeError("Output did not meet Markdown, page-coverage or image-link checks")
        record["state"] = "structural_checks_passed"
        record["markdown_sha256"] = hashlib.sha256(md.read_bytes()).hexdigest()
        return_code = 0
    except Exception as exc:
        record.update(state="failed", error_type=type(exc).__name__, error=str(exc),
                      traceback=traceback.format_exc())
        traceback.print_exc()
        return_code = 1
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        save()
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
