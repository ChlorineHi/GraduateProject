"""Editable DOCX for the full report. The PDF is the typeset copy."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parents[1]


def plain(text: str) -> str:
    return text.replace("`", "")


def set_run_font(run) -> None:
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    run.font.size = Pt(11)


def add_text(paragraph, text: str, size: int = 11, bold: bool = False) -> None:
    run = paragraph.add_run(plain(text))
    run.bold = bold
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    run.font.size = Pt(size)


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/final-report/UrbanNoiseLab_完整系统报告.md"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs/final-report/UrbanNoiseLab_完整系统报告.docx"
    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    lines = source.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            for code_line in block:
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.space_after = Pt(0)
                add_text(paragraph, code_line if code_line else " ", 9)
            i += 1
            continue
        image = re.match(r"!\[(.+)\]\((.+)\)", line)
        if image:
            path = (source.parent / image.group(2)).resolve()
            if path.exists():
                document.add_picture(str(path), width=Cm(15.5))
            caption = document.add_paragraph()
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_text(caption, image.group(1), 9)
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [plain(cell.strip()) for cell in lines[i].strip("|").split("|")]
                if not all(set(cell) <= set("-: ") for cell in cells):
                    rows.append(cells)
                i += 1
            if rows:
                cols = max(len(row) for row in rows)
                table = document.add_table(rows=len(rows), cols=cols)
                table.style = "Table Grid"
                for r, row in enumerate(rows):
                    for c in range(cols):
                        text = row[c] if c < len(row) else ""
                        table.cell(r, c).text = ""
                        paragraph = table.cell(r, c).paragraphs[0]
                        add_text(paragraph, text, 8, bold=(r == 0))
            continue
        if line.startswith("# "):
            paragraph = document.add_heading(plain(line[2:].strip()), level=1)
        elif line.startswith("## "):
            paragraph = document.add_heading(plain(line[3:].strip()), level=2)
        elif line.startswith("### "):
            paragraph = document.add_heading(plain(line[4:].strip()), level=3)
        elif line.strip():
            paragraph = document.add_paragraph()
            add_text(paragraph, line.strip(), 11)
        i += 1
    document.save(target)
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
