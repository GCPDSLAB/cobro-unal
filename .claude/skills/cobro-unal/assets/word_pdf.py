#!/usr/bin/env python3
"""Export .docx files to PDF through Microsoft Word.

Word must write inside the user's home directory: its sandbox blocks paths such
as /tmp and the AppleScript call then hangs on an invisible permission prompt.

Usage:
    word_pdf.py FILE.docx [FILE.docx ...] [--outdir DIR]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HOME = pathlib.Path.home()

SCRIPT = """with timeout of 600 seconds
tell application "Microsoft Word"
  set displayAlerts to none
  open POSIX file "{docx}"
  set theDoc to document "{name}"
  save as theDoc file name "{pdf}" file format format PDF
  close theDoc saving no
end tell
end timeout
"""


def export(docx: pathlib.Path, pdf: pathlib.Path) -> str | None:
    # Address the document by name, never `active document`: if the open
    # silently fails, `active document` would export whatever else Word had open.
    script = SCRIPT.format(docx=str(docx), pdf=str(pdf), name=docx.name)
    result = subprocess.run(["osascript", "-"], input=script, capture_output=True, text=True)
    if result.returncode != 0:
        return result.stderr.strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=pathlib.Path)
    parser.add_argument("--outdir", type=pathlib.Path)
    args = parser.parse_args()

    report = []
    failed = 0
    for item in args.files:
        docx = item.resolve()
        outdir = (args.outdir.resolve() if args.outdir else docx.parent)
        pdf = outdir / (docx.stem + ".pdf")
        if HOME not in pdf.parents:
            report.append({"docx": str(docx), "ok": False,
                           "detail": "target outside the home directory; Word cannot write there"})
            failed += 1
            continue
        outdir.mkdir(parents=True, exist_ok=True)
        error = export(docx, pdf)
        report.append({"docx": str(docx), "pdf": str(pdf), "ok": error is None,
                       "detail": error or "exported"})
        failed += error is not None

    print(json.dumps({"exported": report, "failed": failed}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
