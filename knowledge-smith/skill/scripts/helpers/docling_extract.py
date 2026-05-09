#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["docling>=2"]
# ///
"""Convert a PDF to markdown using docling. Writes markdown to stdout.

Kept in its own PEP 723 script so the main `ingest_pdf.py` doesn't pay
the docling install cost when the agent picks tier-1 (metadata only) or
tier-2 (pdftotext). Only invoked from `ingest_pdf.py --docling`.

First run pulls hundreds of MB of layout/OCR models into the docling
cache (~/.cache/docling). Subsequent runs are fast.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pdf", help="path to the PDF")
    args = p.parse_args(argv)

    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.is_file():
        print(f"not a file: {pdf}", file=sys.stderr)
        return 2

    from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]

    converter = DocumentConverter()
    result = converter.convert(str(pdf))
    sys.stdout.write(result.document.export_to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
