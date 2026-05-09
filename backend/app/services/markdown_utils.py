from __future__ import annotations

import re


_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_SEPARATOR_RE = re.compile(r"\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?")


def _normalize_compact_table_fragment(fragment: str) -> str:
    text = fragment.strip()
    if text.count("|") < 6 or not _SEPARATOR_RE.search(text):
        return fragment
    # Compact form usually looks like: | h1 | h2 | |---|---| | v1 | v2 |
    normalized = re.sub(r"\|\s+\|", "|\n|", text)
    normalized = re.sub(r"\n{2,}", "\n", normalized).strip()
    lines = [ln.strip() for ln in normalized.splitlines() if ln.strip()]
    if len(lines) >= 3 and all(ln.startswith("|") and ln.endswith("|") for ln in lines[:3]):
        return "\n".join(lines)
    return fragment


def normalize_markdown_tables(text: str) -> str:
    if not text:
        return text

    fences: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        fences.append(match.group(0))
        return f"@@FENCE_{len(fences)-1}@@"

    protected = _FENCE_RE.sub(_stash, text)
    parts = re.split(r"(\n\s*\n)", protected)
    out_parts: list[str] = []
    for part in parts:
        if part.strip() and part.count("|") >= 6 and "|---" in part.replace(" ", ""):
            out_parts.append(_normalize_compact_table_fragment(part))
        else:
            out_parts.append(part)
    restored = "".join(out_parts)

    for idx, block in enumerate(fences):
        restored = restored.replace(f"@@FENCE_{idx}@@", block)
    return restored


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_MD_IMAGE_LABEL_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\s*$")
_TABLE_SEP_LINE_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_OUTPUT_DIR_LINE_RE = re.compile(r"^\s*.*output_dir.*$", re.IGNORECASE)


def sanitize_model_final_answer(text: str) -> str:
    if not text:
        return text
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        line_no_img = _MD_IMAGE_RE.sub("", line).strip()
        if _MD_IMAGE_LABEL_LINE_RE.match(line.strip()):
            continue
        if _TABLE_SEP_LINE_RE.match(line.strip()):
            continue
        # Drop short pipe-only rows often used as broken table/image glue.
        if _TABLE_ROW_RE.match(line.strip()):
            pipes = line.count("|")
            alnum = sum(ch.isalnum() for ch in line)
            if pipes >= 2 and alnum <= 30:
                continue
        if _OUTPUT_DIR_LINE_RE.match(line.strip()) and ("график" in line.lower() or "таблиц" in line.lower() or "output_dir" in line.lower()):
            continue
        if line_no_img:
            cleaned.append(line_no_img)
        else:
            cleaned.append("")

    out = "\n".join(cleaned)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out
