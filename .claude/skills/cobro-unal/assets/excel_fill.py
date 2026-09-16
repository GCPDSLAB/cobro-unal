#!/usr/bin/env python3
"""Fill the UNAL "Certificación determinación cedular" workbook via Microsoft Excel.

Microsoft Excel is driven through AppleScript instead of openpyxl so that the
embedded logo, VML drawings and conditional data validations survive, and so
that every formula is recalculated by Excel itself before the PDF is exported.

Usage:
    excel_fill.py --xlsx BOOK.xlsx --data data.json [--pdf OUT.pdf]

`data.json` maps cell references to typed values:

    {
      "D17": {"t": "s", "v": "NOMBRE APELLIDO CONTRATISTA"},
      "D18": {"t": "n", "v": 1000000000},
      "G23": {"t": "d", "v": "AAAA-MM-DD"}
    }

Types: "s" string, "n" number, "d" ISO date (yyyy-mm-dd).

Prints a JSON report to stdout with the recalculated control values.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys

SHEET = "Certificación Mensual"
HIDE = "Instrucciones"
# Cleared before every fill: the contract block plus the fields that change per
# period. Cells outside this list are always rewritten from the caller's data.
# D36 and E45 are merged cells: clearing only their anchor does nothing, so the
# whole merged range has to be named.
CLEAR_FIRST = ("B23:I27", "D36:E36", "C41", "C42", "E45:E48")

EXCEL_EPOCH = dt.date(1899, 12, 30)
SEPARATOR = "|"

# Recalculated cells read back after filling. The package is validated against
# these, so they are always reported even when the caller does not ask.
READBACK = {
    "aporte_salud": "I36",
    "aporte_pension": "I37",
    "fondo_solidaridad": "I38",
    "aporte_arl": "I39",
    "total_aportes": "I40",
    "valor_mensualizado_total": "B57",
    "ibc_consolidado": "D57",
    "base_retencion_total": "I57",
}


def as_serial(iso: str) -> int:
    """Convert an ISO date to the Excel serial number used by the sheet."""
    return (dt.date.fromisoformat(iso) - EXCEL_EPOCH).days


def applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def literal(cell: str, spec: dict) -> str:
    kind = spec.get("t", "s")
    value = spec["v"]
    if kind == "s":
        return applescript_string(str(value))
    if kind == "n":
        return repr(float(value)) if isinstance(value, float) else str(int(value))
    if kind == "d":
        return str(as_serial(str(value)))
    raise ValueError(f"{cell}: unknown value type {kind!r}")


def build_script(xlsx: pathlib.Path, data: dict, pdf: pathlib.Path | None,
                 clear: bool = True) -> str:
    lines = [
        "with timeout of 600 seconds",
        'tell application "Microsoft Excel"',
        "  set displayAlerts to false",
        # `POSIX file` is required: a bare string path with spaces or
        # parentheses silently fails to open, and `active workbook` then points
        # at whatever else Excel had open — writing to the wrong file while
        # reporting success. Address the workbook by its basename instead.
        f"  open POSIX file {applescript_string(str(xlsx))}",
        f"  set wb to workbook {applescript_string(xlsx.name)}",
        f"  set ws to worksheet {applescript_string(SHEET)} of wb",
    ]
    if clear:
        # The shipped template carries a filled example. Without this, a stale
        # contract row or a leftover "  SI  " in E45 would survive into the
        # period being filled.
        for ref in CLEAR_FIRST:
            lines.append(f"  clear contents range {applescript_string(ref)} of ws")
    for cell, spec in data.items():
        lines.append(
            f"  set value of range {applescript_string(cell)} of ws to {literal(cell, spec)}"
        )
    lines.append("  calculate full")
    lines.append("  save wb")
    if pdf is not None:
        # Excel exports every visible sheet, so hide the instruction sheet to
        # honour the format's rule of submitting only "Certificación Mensual".
        lines.append(f"  set visible of worksheet {applescript_string(HIDE)} of wb to sheet hidden")
        lines.append("  activate object ws")
        lines.append(
            f"  save as ws filename {applescript_string(str(pdf))} file format PDF file format"
        )
        lines.append(f"  set visible of worksheet {applescript_string(HIDE)} of wb to sheet visible")
    lines.append("  set out to {}")
    for cell in READBACK.values():
        # Coerce through an intermediate variable: AppleScript refuses to round
        # a range reference directly, and blank cells are not numbers at all.
        lines.append(f"  set v to value of range {applescript_string(cell)} of ws")
        lines.append("  try")
        lines.append("    set end of out to ((round (v as real)) as integer) as text")
        lines.append("  on error")
        lines.append("    set end of out to v as text")
        lines.append("  end try")
    lines.append("  close wb saving no")
    lines.append("  set displayAlerts to true")
    lines.append(f"  set AppleScript's text item delimiters to {applescript_string(SEPARATOR)}")
    lines.append("  return out as text")
    lines.append("end tell")
    lines.append("end timeout")
    return "\n".join(lines)


def to_number(raw: str) -> float | str:
    cleaned = raw.strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return raw.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", required=True, type=pathlib.Path)
    parser.add_argument("--data", required=True, type=pathlib.Path)
    parser.add_argument("--pdf", type=pathlib.Path)
    parser.add_argument("--no-clear", action="store_true",
                        help="keep existing contents (phase 2, when only C42/E45 change)")
    args = parser.parse_args()

    xlsx = args.xlsx.resolve()
    if not xlsx.is_file():
        print(f"workbook not found: {xlsx}", file=sys.stderr)
        return 1

    data = json.loads(args.data.read_text(encoding="utf-8"))
    pdf = args.pdf.resolve() if args.pdf else None
    script = build_script(xlsx, data, pdf, clear=not args.no_clear)

    result = subprocess.run(
        ["osascript", "-"], input=script, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode

    values = result.stdout.strip().split(SEPARATOR)
    report = {
        "xlsx": str(xlsx),
        "pdf": str(pdf) if pdf else None,
        "cells_written": len(data),
        "cleared": [] if args.no_clear else list(CLEAR_FIRST),
        "valores": {
            name: to_number(values[index])
            for index, name in enumerate(READBACK)
            if index < len(values)
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
