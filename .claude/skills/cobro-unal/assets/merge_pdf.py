#!/usr/bin/env python3
"""Merge the per-contract package into a single PDF, in contractual order.

Pages are copied verbatim, so the scanned contracts keep their original image
quality instead of being re-encoded.

Usage:
    merge_pdf.py --out PAQUETE.pdf part1.pdf part2.pdf ...

Every input must exist: a package missing a support is a rejected package, so
this refuses to produce a partial merge.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

from pypdf import PdfReader, PdfWriter

# Word's PDF export uses cross-reference offsets pypdf repairs but complains
# about on every page; the repair is silent and the output is correct.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("parts", nargs="+", type=pathlib.Path)
    args = parser.parse_args()

    missing = [str(part) for part in args.parts if not part.is_file()]
    if missing:
        print(json.dumps({"ok": False, "missing": missing}, ensure_ascii=False, indent=2))
        return 1

    writer = PdfWriter()
    detail = []
    for part in args.parts:
        reader = PdfReader(str(part))
        for page in reader.pages:
            writer.add_page(page)
        detail.append({"parte": part.name, "paginas": len(reader.pages)})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("wb") as handle:
        writer.write(handle)

    print(json.dumps(
        {"ok": True, "paquete": str(args.out.resolve()),
         "paginas_totales": len(writer.pages), "partes": detail},
        ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
