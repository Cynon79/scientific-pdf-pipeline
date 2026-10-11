#!/usr/bin/env python3
"""
Batch-clean Markdown converted from scientific PDFs for downstream LLM extraction.

This is an initial de-noising pass, not a chunker. It preserves scientific body
content, captions, real Markdown/HTML tables, and equations, while removing common
PDF/web conversion noise such as image links, references, author/COI metadata,
acknowledgments, and supplementary-information tail sections.

MinerU <details> blocks extracted from figures are archived separately as JSONL.
Only high-quality figure-extracted tables are inlined into the cleaned Markdown by
default, because many image-derived curve tables contain approximate or mostly
empty values that can pollute LLM extraction.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path


IMAGE_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*(?:<br\s*/?>)?\s*$", re.I)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
DETAILS_OPEN_RE = re.compile(r"^\s*<details>\s*$", re.I)
DETAILS_CLOSE_RE = re.compile(r"^\s*</details>\s*$", re.I)
SUMMARY_RE = re.compile(r"^\s*<summary>\s*(.*?)\s*</summary>\s*$", re.I)
TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
CAPTION_RE = re.compile(r"^\s*(fig(?:ure)?\.?|scheme|table)\s*[\w\d]+[.\s:]", re.I)


HARD_DROP_SECTION_PREFIXES = (
    "references",
    "reference",
    "bibliography",
)


SOFT_DROP_SECTION_PREFIXES = (
    "acknowledgment",
    "acknowledgement",
    "acknowledgments",
    "acknowledgements",
    "author information",
    "author contributions",
    "authors",
    "corresponding authors",
    "credit authorship contribution statement",
    "declaration of competing interest",
    "declaration of competing interests",
    "competing interest",
    "competing interests",
    "conflict of interest",
    "conflicts of interest",
    "data availability",
    "associated content",
    "supporting information",
    "supplementary information",
    "supplementary data",
    "appendix a. supplementary data",
    "notes",
)


JUNK_LINE_PATTERNS = (
    re.compile(r"^\s*(read online|access|metrics\s*&\s*more|article recommendations)\s*$", re.I),
    re.compile(r"^\s*(article|full length article|research article|open access)\s*$", re.I),
    re.compile(r"^\s*supporting information\s*$", re.I),
    re.compile(r"^\s*www\.[^\s]+$", re.I),
    re.compile(r"^\s*https?://(?:dx\.)?doi\.org/[^\s]+\.?$", re.I),
    re.compile(r"^\s*doi:\s*\S+\s*$", re.I),
    re.compile(r"^\s*copyright\s+©.*$", re.I),
    re.compile(r"^\s*©\s*\d{4}\s+.*$", re.I),
)


@dataclass
class CleanStats:
    file: str
    input_chars: int
    output_chars: int
    input_lines: int
    output_lines: int
    removed_image_lines: int = 0
    removed_junk_lines: int = 0
    removed_sections: int = 0
    removed_section_lines: int = 0
    archived_detail_blocks: int = 0
    inlined_detail_blocks: int = 0
    skipped_detail_blocks: int = 0
    high_quality_detail_blocks: int = 0
    medium_quality_detail_blocks: int = 0
    low_quality_detail_blocks: int = 0


DOMAIN_KEYWORDS = (
    "atomic",
    "element",
    "composition",
    "eds",
    "icp",
    "xps",
    "binding energy",
    "oxidation state",
    "xrd",
    "2θ",
    "2 theta",
    "bet",
    "surface area",
    "pore",
    "removal",
    "degradation",
    "conversion",
    "selectivity",
    "rate constant",
    "toc",
    "overpotential",
    "current density",
    "tafel",
    "scavenger",
    "radical",
    "epr",
    "adsorption energy",
    "free energy",
    "dft",
    "band gap",
    "mott",
    "photocatal",
)


PLACEHOLDER_VALUES = {
    "",
    "-",
    "--",
    "—",
    "–",
    "n/a",
    "na",
    "nan",
    "none",
    "null",
    "category",
    "value",
    "low",
    "high",
    "series",
}


def normalize_heading(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"[*_`\\#]+", "", text)
    text = text.replace("ı", "i").replace("İ", "I")
    text = re.sub(r"\s+", " ", text)
    spaced_caps = re.fullmatch(r"(?:[A-Za-z]\s+){2,}[A-Za-z]", text)
    if spaced_caps:
        text = text.replace(" ", "")
    return text.strip(" .:;-").lower()


def should_drop_heading(raw_heading: str) -> bool:
    return drop_heading_kind(raw_heading) is not None


def drop_heading_kind(raw_heading: str) -> str | None:
    heading = normalize_heading(raw_heading)
    if any(heading.startswith(prefix) for prefix in HARD_DROP_SECTION_PREFIXES):
        return "hard"
    if any(heading.startswith(prefix) for prefix in SOFT_DROP_SECTION_PREFIXES):
        return "soft"
    return any(
        phrase in heading
        for phrase in (
            "supporting information",
            "supplementary information",
            "supplementary data",
        )
    ) and "hard" or None


def is_content_resumption_line(line: str) -> bool:
    stripped = line.strip()
    return bool(
        stripped
        and (
            DETAILS_OPEN_RE.match(stripped)
            or IMAGE_LINE_RE.match(stripped)
            or TABLE_LINE_RE.match(stripped)
            or CAPTION_RE.match(stripped)
            or re.match(r"^table\s+\d+", stripped, re.I)
        )
    )


def is_junk_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(pattern.match(stripped) for pattern in JUNK_LINE_PATTERNS)


def collapse_blank_lines(lines: list[str], max_blank: int = 1) -> list[str]:
    collapsed: list[str] = []
    blank_count = 0
    for line in lines:
        if line.strip():
            blank_count = 0
            collapsed.append(line.rstrip())
        else:
            blank_count += 1
            if blank_count <= max_blank:
                collapsed.append("")
    while collapsed and not collapsed[0].strip():
        collapsed.pop(0)
    while collapsed and not collapsed[-1].strip():
        collapsed.pop()
    return collapsed


def parse_table_cells(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def normalize_cell(cell: str) -> str:
    text = re.sub(r"<[^>]+>", "", cell).strip().lower()
    text = text.replace("~", "").replace("≈", "").replace("−", "-")
    text = re.sub(r"\s+", " ", text)
    return text


def is_zeroish(cell: str) -> bool:
    text = normalize_cell(cell)
    if text in {"0", "0.0", "0.00", "-0", "-0.0"}:
        return True
    return bool(re.fullmatch(r"-?0(?:\.0+)?(?:\s*(?:%|a\.u\.|au))?", text))


def looks_numeric(cell: str) -> bool:
    text = normalize_cell(cell)
    return bool(re.search(r"-?\d+(?:\.\d+)?", text))


def extract_detail_block(block_lines: list[str]) -> tuple[str, list[str]]:
    summary = ""
    content: list[str] = []
    for line in block_lines:
        if DETAILS_OPEN_RE.match(line) or DETAILS_CLOSE_RE.match(line):
            continue
        summary_match = SUMMARY_RE.match(line)
        if summary_match:
            summary = summary_match.group(1).strip()
            continue
        content.append(line.rstrip())
    return summary, collapse_blank_lines(content, max_blank=1)


def find_near_caption(lines: list[str], start: int, end: int) -> str:
    for idx in range(end + 1, min(len(lines), end + 20)):
        candidate = lines[idx].strip()
        if CAPTION_RE.match(candidate):
            return candidate
    for idx in range(start - 1, max(-1, start - 12), -1):
        candidate = lines[idx].strip()
        if CAPTION_RE.match(candidate):
            return candidate
    return ""


def score_detail_block(summary: str, content_lines: list[str], near_caption: str) -> dict[str, object]:
    content_text = "\n".join(content_lines)
    table_lines = [line for line in content_lines if TABLE_LINE_RE.match(line)]
    separator_lines = [line for line in table_lines if TABLE_SEPARATOR_RE.match(line)]
    data_table_lines = [line for line in table_lines if line not in separator_lines]
    cells = [cell for line in data_table_lines for cell in parse_table_cells(line)]
    header_cells = parse_table_cells(data_table_lines[0]) if data_table_lines else []
    data_cells = [
        cell
        for line in data_table_lines[1:]
        for cell in parse_table_cells(line)
    ]
    value_cells = cells
    nonempty_cells = [cell for cell in value_cells if normalize_cell(cell)]
    zeroish_cells = [cell for cell in nonempty_cells if is_zeroish(cell)]
    placeholder_cells = [cell for cell in nonempty_cells if normalize_cell(cell) in PLACEHOLDER_VALUES]
    numeric_cells = [cell for cell in nonempty_cells if looks_numeric(cell)]
    combined = f"{summary}\n{near_caption}\n{content_text}".lower()
    domain_hits = sorted({keyword for keyword in DOMAIN_KEYWORDS if keyword in combined})

    nonempty_ratio = len(nonempty_cells) / len(value_cells) if value_cells else 0.0
    zeroish_ratio = len(zeroish_cells) / len(nonempty_cells) if nonempty_cells else 1.0
    placeholder_ratio = len(placeholder_cells) / len(nonempty_cells) if nonempty_cells else 1.0
    numeric_ratio = len(numeric_cells) / len(nonempty_cells) if nonempty_cells else 0.0
    has_table = bool(table_lines)
    header_text = " ".join(header_cells).lower()
    metric_header = any(
        token in header_text
        for token in (
            "sample",
            "element",
            "overpotential",
            "conversion",
            "selectivity",
            "surface",
            "pore",
            "removal",
            "degradation",
            "rate",
            "band",
            "adsorption",
            "free energy",
        )
    )
    curve_axis_header = any(
        token in header_text
        for token in (
            "intensity",
            "2 theta",
            "2θ",
            "binding energy",
            "potential",
            "time",
            "z'",
            "-z",
        )
    )
    scientific_label_cells = [
        cell
        for cell in data_cells
        if re.search(
            r"\b(?:Fe|Co|Ni|Cr|Mn|Cu|Al|Zn|Bi|Ce|Mo|O|Ru|Pd|Pt|Ir)\b|"
            r"[A-Z][a-z]?[²³⁴]?[+-]|p[₁₂₃0-9/]+|sat\.?|O[_ -]?(?:v|lat|L)|M-O|OH",
            cell,
        )
    ]

    reasons: list[str] = []
    if not content_text.strip():
        quality = "low"
        reasons.append("empty detail content")
    elif not has_table:
        quality = "medium" if len(content_text) > 80 and domain_hits else "low"
        reasons.append("no markdown table")
    elif len(nonempty_cells) < 6:
        quality = "low"
        reasons.append("too few non-empty table cells")
    elif nonempty_ratio < 0.35:
        quality = "low"
        reasons.append("mostly empty table cells")
    elif zeroish_ratio >= 0.70:
        quality = "low"
        reasons.append("mostly zero-like values")
    elif placeholder_ratio >= 0.45:
        quality = "low"
        reasons.append("many placeholder labels")
    elif domain_hits and nonempty_ratio >= 0.60 and zeroish_ratio < 0.45:
        quality = "high"
        reasons.append("domain-relevant table with sufficient non-empty values")
    elif len(data_table_lines) >= 3 and nonempty_ratio >= 0.50 and zeroish_ratio < 0.60:
        quality = "medium"
        reasons.append("usable table but weak domain signal or many approximate values")
    else:
        quality = "low"
        reasons.append("weak or noisy extracted table")

    if (
        quality == "high"
        and curve_axis_header
        and not metric_header
        and len(scientific_label_cells) < 2
    ):
        quality = "medium"
        reasons.append("axis-curve table without robust scientific labels")

    return {
        "summary": summary,
        "quality": quality,
        "reason": "; ".join(reasons),
        "near_caption": near_caption,
        "has_table": has_table,
        "table_line_count": len(table_lines),
        "data_table_line_count": len(data_table_lines),
        "cell_count": len(value_cells),
        "nonempty_cell_count": len(nonempty_cells),
        "nonempty_ratio": round(nonempty_ratio, 3),
        "zeroish_ratio": round(zeroish_ratio, 3),
        "placeholder_ratio": round(placeholder_ratio, 3),
        "numeric_ratio": round(numeric_ratio, 3),
        "curve_axis_header": curve_axis_header,
        "metric_header": metric_header,
        "scientific_label_cell_count": len(scientific_label_cells),
        "domain_keywords": domain_hits,
        "content": content_text,
    }


def should_inline_detail(record: dict[str, object], mode: str) -> bool:
    if mode == "all":
        return True
    if mode == "none":
        return False
    return record.get("quality") == "high"


def clean_markdown(
    text: str,
    filename: str,
    inline_details: str = "high",
) -> tuple[str, CleanStats, list[dict[str, object]]]:
    lines = text.splitlines()
    stats = CleanStats(
        file=filename,
        input_chars=len(text),
        output_chars=0,
        input_lines=len(lines),
        output_lines=0,
    )

    cleaned: list[str] = []
    detail_records: list[dict[str, object]] = []
    drop_level: int | None = None
    drop_kind: str | None = None
    i = 0

    while i < len(lines):
        line = lines[i]
        heading_match = HEADING_RE.match(line)

        if drop_level is not None:
            if heading_match and len(heading_match.group(1)) <= drop_level:
                drop_level = None
                drop_kind = None
            elif drop_kind == "soft" and is_content_resumption_line(line):
                drop_level = None
                drop_kind = None
            else:
                stats.removed_section_lines += 1
                i += 1
                continue

        if heading_match and (kind := drop_heading_kind(heading_match.group(2))):
            drop_level = len(heading_match.group(1))
            drop_kind = kind
            stats.removed_sections += 1
            stats.removed_section_lines += 1
            i += 1
            continue

        if IMAGE_LINE_RE.match(line):
            stats.removed_image_lines += 1
            i += 1
            continue

        if DETAILS_OPEN_RE.match(line):
            start = i
            block_lines = [line]
            i += 1
            while i < len(lines):
                block_lines.append(lines[i])
                if DETAILS_CLOSE_RE.match(lines[i]):
                    break
                i += 1
            end = i
            summary, content_lines = extract_detail_block(block_lines)
            near_caption = find_near_caption(lines, start, end)
            record = score_detail_block(summary, content_lines, near_caption)
            record.update(
                {
                    "file": filename,
                    "block_index": len(detail_records) + 1,
                    "start_line": start + 1,
                    "end_line": end + 1,
                }
            )
            detail_records.append(record)
            stats.archived_detail_blocks += 1
            quality = str(record["quality"])
            if quality == "high":
                stats.high_quality_detail_blocks += 1
            elif quality == "medium":
                stats.medium_quality_detail_blocks += 1
            else:
                stats.low_quality_detail_blocks += 1

            if should_inline_detail(record, inline_details):
                summary_label = summary or "figure_extraction"
                cleaned.append(f"[figure_extraction:{quality}: {summary_label}]")
                cleaned.extend(content_lines)
                stats.inlined_detail_blocks += 1
            else:
                stats.skipped_detail_blocks += 1
            i += 1
            continue

        if DETAILS_CLOSE_RE.match(line):
            i += 1
            continue

        summary_match = SUMMARY_RE.match(line)
        if summary_match:
            i += 1
            continue

        if is_junk_line(line):
            stats.removed_junk_lines += 1
            i += 1
            continue

        cleaned.append(line.rstrip())
        i += 1

    cleaned = collapse_blank_lines(cleaned, max_blank=1)
    output = "\n".join(cleaned) + ("\n" if cleaned else "")
    stats.output_chars = len(output)
    stats.output_lines = len(cleaned)
    return output, stats, detail_records


def iter_input_files(input_dir: Path, limit: int | None, files: list[str] | None) -> list[Path]:
    if files:
        selected = [input_dir / name for name in files]
    else:
        selected = sorted(input_dir.glob("*.md"))
        if limit is not None:
            selected = selected[:limit]
    missing = [path for path in selected if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing input files: " + ", ".join(str(p) for p in missing))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-clean PDF-converted Markdown files.")
    parser.add_argument("--input", default="MD_all", help="Input directory containing .md files.")
    parser.add_argument("--output", default="MD_clean", help="Output directory for cleaned .md files.")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N sorted .md files.")
    parser.add_argument("--files", nargs="*", default=None, help="Specific filenames under --input to process.")
    parser.add_argument("--refresh", action="store_true", help="Delete and recreate output directory if it exists.")
    parser.add_argument(
        "--drop-details",
        action="store_true",
        help="Backward-compatible alias for --inline-details none.",
    )
    parser.add_argument(
        "--inline-details",
        choices=("high", "none", "all"),
        default="high",
        help="Which archived MinerU <details> blocks to inline into cleaned Markdown. Default: high.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if output_dir.exists():
        if args.refresh:
            shutil.rmtree(output_dir)
        else:
            raise FileExistsError(f"Output exists: {output_dir}. Use --refresh or choose another output.")
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_tables_dir = output_dir / "figure_tables"
    figure_tables_dir.mkdir(parents=True, exist_ok=True)

    files = iter_input_files(input_dir, args.limit, args.files)
    report_path = output_dir / "clean_report.csv"

    stats_rows: list[CleanStats] = []
    inline_details = "none" if args.drop_details else args.inline_details
    for path in files:
        raw = path.read_text(encoding="utf-8", errors="replace")
        cleaned, stats, detail_records = clean_markdown(raw, path.name, inline_details=inline_details)
        (output_dir / path.name).write_text(cleaned, encoding="utf-8")
        figure_jsonl = figure_tables_dir / f"{path.stem}.jsonl"
        with figure_jsonl.open("w", encoding="utf-8") as f:
            for record in detail_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        stats_rows.append(stats)

    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(stats_rows[0]).keys()) if stats_rows else [])
        if stats_rows:
            writer.writeheader()
            for row in stats_rows:
                writer.writerow(asdict(row))

    print(f"input_dir\t{input_dir}")
    print(f"output_dir\t{output_dir}")
    print(f"processed_files\t{len(stats_rows)}")
    print(f"report\t{report_path}")
    print(f"figure_tables_dir\t{figure_tables_dir}")
    print(f"inline_details\t{inline_details}")
    if stats_rows:
        print(f"removed_image_lines\t{sum(s.removed_image_lines for s in stats_rows)}")
        print(f"removed_sections\t{sum(s.removed_sections for s in stats_rows)}")
        print(f"removed_section_lines\t{sum(s.removed_section_lines for s in stats_rows)}")
        print(f"archived_detail_blocks\t{sum(s.archived_detail_blocks for s in stats_rows)}")
        print(f"inlined_detail_blocks\t{sum(s.inlined_detail_blocks for s in stats_rows)}")
        print(f"skipped_detail_blocks\t{sum(s.skipped_detail_blocks for s in stats_rows)}")
        print(f"high_quality_detail_blocks\t{sum(s.high_quality_detail_blocks for s in stats_rows)}")
        print(f"medium_quality_detail_blocks\t{sum(s.medium_quality_detail_blocks for s in stats_rows)}")
        print(f"low_quality_detail_blocks\t{sum(s.low_quality_detail_blocks for s in stats_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
