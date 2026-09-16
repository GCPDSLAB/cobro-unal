#!/usr/bin/env python3
"""Fill the UNAL Word formats (constancia / informe) from a JSON operation list.

The templates are edited in place through python-docx so the UNAL logo, headers
and table borders survive untouched. Addressing is by raw grid coordinates
(`tr` / `tc` on the XML rows and cells), because both templates use merged
cells that make python-docx's `row.cells` view collapse.

Usage:
    docx_fill.py --docx FILE.docx --ops ops.json [--out OUT.docx]

ops.json:
    {"ops": [
      {"op": "replace", "old": "[SEDE]", "new": "SEDE MANIZALES"},
      {"op": "set_cell", "scope": "header", "table": 1, "tr": 0, "tc": 1,
       "text": "NOMBRE APELLIDO CONTRATISTA"},
      {"op": "blanks", "scope": "body", "table": 0, "tr": 5, "tc": 0,
       "texts": ["9876543210", "02/09/2026", "SEPTIEMBRE DE 2026"]},
      {"op": "checkbox", "scope": "body", "table": 0, "tr": 6, "tc": 0, "index": 2},
      {"op": "ensure_rows", "scope": "body", "table": 1, "count": 10}
    ]}

Every op is applied in order and reported on stdout as JSON.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import re
import sys

import docx
from docx.oxml.ns import qn

BLANK = re.compile(r"_{3,}")
UNCHECKED = "☐"
CHECKED = "☒"


def tables_for(document, scope: str):
    if scope == "body":
        return document.tables
    section = document.sections[0]
    if scope == "header":
        return section.header.tables
    if scope == "footer":
        return section.footer.tables
    raise ValueError(f"unknown scope {scope!r}")


def paragraphs_for(document, scope: str):
    if scope == "body":
        return document.paragraphs
    section = document.sections[0]
    if scope == "header":
        return section.header.paragraphs
    if scope == "footer":
        return section.footer.paragraphs
    raise ValueError(f"unknown scope {scope!r}")


def flatten_content_controls(document) -> int:
    """Replace every `w:sdt` with its content, everywhere in the document.

    The constancia wraps its modalidad dropdown in a `w:sdt` that sits as a
    sibling of `w:tc` inside the row, which silently shifts every column index,
    and a control left in place keeps printing its own placeholder instead of
    the text written next to it. Flattening removes both problems at once.
    """
    removed = 0
    roots = [document.element.body]
    section = document.sections[0]
    for part in (section.header, section.footer):
        roots.append(part._element)

    for root in roots:
        while True:
            node = root.find(".//" + qn("w:sdt"))
            if node is None:
                break
            parent = node.getparent()
            index = list(parent).index(node)
            content = node.find(qn("w:sdtContent"))
            children = list(content) if content is not None else []
            for offset, child in enumerate(children):
                parent.insert(index + offset, child)
            parent.remove(node)
            removed += 1
    return removed


def grid_cell(table, tr: int, tc: int):
    """Address a cell by its raw XML position, ignoring merge expansion."""
    rows = table._tbl.findall(qn("w:tr"))
    cells = rows[tr].findall(qn("w:tc"))
    return cells[tc]


def cell_paragraphs(tc):
    return tc.findall(qn("w:p"))


def paragraph_text(node) -> str:
    return "".join(t.text or "" for t in node.iter(qn("w:t")))


def set_paragraph_text(node, text: str) -> None:
    """Rewrite the paragraph as a single run, keeping its character formatting.

    Everything except `w:pPr` is dropped, content controls (`w:sdt`) included:
    both templates wrap their dropdowns and ballot boxes in content controls,
    and a control left in place keeps rendering its own placeholder in Word no
    matter what text sits next to it.
    """
    first_run = node.find(".//" + qn("w:r"))
    run_properties = None
    if first_run is not None:
        found = first_run.find(qn("w:rPr"))
        if found is not None:
            run_properties = copy.deepcopy(found)

    for child in list(node):
        if child.tag != qn("w:pPr"):
            node.remove(child)

    run = node.makeelement(qn("w:r"), {})
    if run_properties is not None:
        run.append(run_properties)
    t = run.makeelement(qn("w:t"), {})
    t.set(qn("xml:space"), "preserve")
    t.text = text
    run.append(t)
    node.append(run)


def replace_span(node, start: int, end: int, text: str) -> bool:
    """Replace characters [start, end) of the paragraph's concatenated text.

    Edits the single `w:t` that holds the span whenever possible, so runs,
    fonts and line breaks around it survive. Returns True when that fast path
    applied, False when the paragraph had to be rebuilt.
    """
    offset = 0
    for t in node.iter(qn("w:t")):
        current = t.text or ""
        if offset <= start and end <= offset + len(current):
            t.text = current[: start - offset] + text + current[end - offset :]
            return True
        offset += len(current)
    joined = paragraph_text(node)
    set_paragraph_text(node, joined[:start] + text + joined[end:])
    return False


def replace_in_paragraph(node, old: str, new: str) -> bool:
    """Replace inside a single run when possible, else merge and replace."""
    for t in node.iter(qn("w:t")):
        if old in (t.text or ""):
            t.text = t.text.replace(old, new)
            return True
    joined = paragraph_text(node)
    if old not in joined:
        return False
    set_paragraph_text(node, joined.replace(old, new))
    return True


def replace_everywhere(document, old: str, new: str) -> int:
    hits = 0
    for scope in ("body", "header", "footer"):
        for node in (p._p for p in paragraphs_for(document, scope)):
            hits += replace_in_paragraph(node, old, new)
        for table in tables_for(document, scope):
            for tr in table._tbl.findall(qn("w:tr")):
                for tc in tr.findall(qn("w:tc")):
                    for node in cell_paragraphs(tc):
                        hits += replace_in_paragraph(node, old, new)
    return hits


def set_cell_text(document, scope: str, table: int, tr: int, tc: int, text: str) -> None:
    cell = grid_cell(tables_for(document, scope)[table], tr, tc)
    paragraphs = cell_paragraphs(cell)
    set_paragraph_text(paragraphs[0], text)
    for extra in paragraphs[1:]:
        cell.remove(extra)


def fill_blanks(document, scope: str, table: int, tr: int, tc: int, texts: list) -> int:
    """Fill the runs of underscores inside one cell, left to right.

    `texts` is positional: entry i goes into the i-th blank of the cell, and a
    null entry leaves that blank untouched. Filling happens in one pass because
    replacing a blank removes it, which would shift every later index.
    """
    cell = grid_cell(tables_for(document, scope)[table], tr, tc)
    nodes = cell_paragraphs(cell)
    spans = [
        (node_index, match.span())
        for node_index, node in enumerate(nodes)
        for match in BLANK.finditer(paragraph_text(node))
    ]
    if len(texts) > len(spans):
        raise IndexError(
            f"cell ({tr},{tc}) of table {table} has {len(spans)} blank(s), got {len(texts)} value(s)"
        )
    filled = 0
    # Right to left so earlier spans keep their offsets.
    for index in range(len(texts) - 1, -1, -1):
        if texts[index] is None:
            continue
        node_index, (start, end) = spans[index]
        replace_span(nodes[node_index], start, end, str(texts[index]))
        filled += 1
    return filled


def tick(document, scope: str, table: int, tr: int, tc: int, index: int) -> None:
    """Mark the `index`-th ballot box inside one cell as checked.

    Checked and unchecked boxes are both counted, so indices stay absolute no
    matter how many ticks were already applied to the same cell.
    """
    cell = grid_cell(tables_for(document, scope)[table], tr, tc)
    seen = 0
    for node in cell_paragraphs(cell):
        joined = paragraph_text(node)
        positions = [i for i, char in enumerate(joined) if char in (UNCHECKED, CHECKED)]
        if seen + len(positions) <= index:
            seen += len(positions)
            continue
        at = positions[index - seen]
        replace_span(node, at, at + 1, CHECKED)
        return
    raise IndexError(f"checkbox #{index} not found in table {table} cell ({tr},{tc})")


def ensure_rows(document, scope: str, table: int, count: int, template_row: int = -1) -> int:
    """Grow a table to `count` data rows by cloning `template_row`."""
    tbl = tables_for(document, scope)[table]._tbl
    rows = tbl.findall(qn("w:tr"))
    source = rows[template_row]
    added = 0
    while len(tbl.findall(qn("w:tr"))) < count:
        clone = copy.deepcopy(source)
        for tc in clone.findall(qn("w:tc")):
            for node in cell_paragraphs(tc):
                set_paragraph_text(node, "")
        source.addnext(clone)
        source = clone
        added += 1
    return added


def apply(document, op: dict) -> str:
    kind = op["op"]
    if kind == "replace":
        hits = replace_everywhere(document, op["old"], op["new"])
        return f"replace {op['old']!r} -> {hits} hit(s)"
    if kind == "set_cell":
        set_cell_text(document, op.get("scope", "body"), op["table"], op["tr"], op["tc"], op["text"])
        return f"set_cell {op.get('scope','body')}:{op['table']}({op['tr']},{op['tc']})"
    if kind == "blanks":
        filled = fill_blanks(
            document, op.get("scope", "body"), op["table"], op["tr"], op["tc"], op["texts"]
        )
        return f"blanks {op['table']}({op['tr']},{op['tc']}) -> {filled} filled"
    if kind == "checkbox":
        tick(document, op.get("scope", "body"), op["table"], op["tr"], op["tc"], op["index"])
        return f"checkbox #{op['index']} in {op['table']}({op['tr']},{op['tc']})"
    if kind == "ensure_rows":
        added = ensure_rows(
            document, op.get("scope", "body"), op["table"], op["count"], op.get("template_row", -1)
        )
        return f"ensure_rows table {op['table']} -> +{added}"
    raise ValueError(f"unknown op {kind!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docx", required=True, type=pathlib.Path)
    parser.add_argument("--ops", required=True, type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()

    document = docx.Document(str(args.docx))
    flattened = flatten_content_controls(document)
    ops = json.loads(args.ops.read_text(encoding="utf-8"))["ops"]

    log = []
    for index, op in enumerate(ops):
        try:
            log.append({"i": index, "ok": True, "detail": apply(document, op)})
        except Exception as error:  # surface the failing op, keep the rest legible
            log.append({"i": index, "ok": False, "detail": f"{type(error).__name__}: {error}"})

    out = (args.out or args.docx).resolve()
    document.save(str(out))
    failed = [entry for entry in log if not entry["ok"]]
    print(json.dumps({"docx": str(out), "content_controls_flattened": flattened,
                      "applied": log, "failed": len(failed)},
                     ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
