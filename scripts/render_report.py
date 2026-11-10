"""Render the Chinese system report to PDF with fpdf2.

The Markdown file remains the source. This script handles the headings,
tables, fenced code, and images used by that report. It is not a general
Markdown engine.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs/final-report/UrbanNoiseLab_系统完整报告.md"
PDF = ROOT / "docs/final-report/UrbanNoiseLab_系统完整报告.pdf"
FONT = Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc")
MONO = Path("/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf")


class Report(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("wqy", size=8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, f"{self.page_no()}", align="C")


def usable_width(pdf: FPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def plain(text: str) -> str:
    """Drop Markdown inline code markers. Italics are removed in the source."""
    return text.replace("`", "")


def write_rich(pdf: FPDF, text: str, size: float = 11) -> None:
    pdf.set_font("wqy", size=size)
    pdf.set_text_color(28, 32, 28)
    pdf.multi_cell(usable_width(pdf), size * 0.72, plain(text), align="L")
    pdf.ln(1.5)


def write_code(pdf: FPDF, text: str) -> None:
    pdf.set_fill_color(244, 241, 232)
    pdf.set_text_color(28, 32, 28)
    # WenQuanYi covers the Chinese comments inside fenced blocks.
    # JetBrains Mono does not, and missing glyphs become boxes.
    pdf.set_font("wqy", size=8)
    width = usable_width(pdf)
    for line in text.splitlines() or [""]:
        remaining = line if line else " "
        while remaining:
            cut = min(len(remaining), 64)
            while cut > 1 and pdf.get_string_width(remaining[:cut]) > width - 4:
                cut -= 1
            chunk = remaining[:cut]
            pdf.set_x(pdf.l_margin)
            pdf.cell(pdf.get_string_width(chunk) + 1.2, 4.6, chunk, fill=True, new_x="LMARGIN", new_y="NEXT")
            remaining = remaining[cut:]
    pdf.ln(2)


def _wrap_cell(pdf: FPDF, text: str, width: float) -> list[str]:
    lines: list[str] = []
    buf = ""
    for ch in text:
        trial = buf + ch
        if buf and pdf.get_string_width(trial) > width - 1.4:
            lines.append(buf)
            buf = ch
        else:
            buf = trial
    if buf or not lines:
        lines.append(buf)
    return lines


def write_table(pdf: FPDF, rows: list[list[str]]) -> None:
    if not rows:
        return
    cols = max(len(row) for row in rows)
    width = usable_width(pdf) / cols
    for index, row in enumerate(rows):
        cells = row + [""] * (cols - len(row))
        pdf.set_font("wqy", size=7)
        wrapped = [_wrap_cell(pdf, plain(cell), width) for cell in cells]
        row_h = max(len(lines) for lines in wrapped) * 3.8 + 1.8
        if pdf.get_y() + row_h > pdf.h - 18:
            pdf.add_page()
        x0 = pdf.get_x()
        y0 = pdf.get_y()
        if index == 0:
            pdf.set_fill_color(226, 232, 220)
        else:
            pdf.set_fill_color(252, 251, 246)
        for col, lines in enumerate(wrapped):
            x = x0 + col * width
            pdf.rect(x, y0, width, row_h, style="DF")
            pdf.set_xy(x + 0.5, y0 + 0.4)
            pdf.multi_cell(width - 1.0, 3.8, "\n".join(lines), align="L")
        pdf.set_xy(x0, y0 + row_h)
    pdf.ln(3)


def add_image(pdf: FPDF, path: Path, caption: str) -> None:
    if not path.exists():
        write_rich(pdf, f"[缺少图片 {path.name}]")
        return
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
    max_w = usable_width(pdf)
    max_h = 175 if height > width else 118
    draw_w = max_w
    draw_h = draw_w * height / width
    if draw_h > max_h:
        draw_h = max_h
        draw_w = draw_h * width / height
    if pdf.get_y() + draw_h > pdf.h - 22:
        pdf.add_page()
    pdf.image(str(path), w=draw_w, h=draw_h)
    write_rich(pdf, caption, 9)


def render(source: Path | None = None, target: Path | None = None) -> None:
    if not FONT.exists():
        raise SystemExit(f"missing font {FONT}")
    md_path = source or MD
    pdf_path = target or PDF
    text = md_path.read_text(encoding="utf-8")
    pdf = Report(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_font("wqy", "", str(FONT))
    pdf.add_font("mono", "", str(MONO))
    pdf.set_margins(16, 16, 16)
    pdf.add_page()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            write_code(pdf, "\n".join(block))
            i += 1
            continue
        image = re.match(r"!\[(.+)\]\((.+)\)", line)
        if image:
            add_image(pdf, (md_path.parent / image.group(2)).resolve(), image.group(1))
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [cell.strip() for cell in lines[i].strip("|").split("|")]
                if not all(set(cell) <= set("-: ") for cell in cells):
                    rows.append(cells)
                i += 1
            write_table(pdf, rows)
            continue
        if line.startswith("# "):
            pdf.set_font("wqy", size=16)
            pdf.multi_cell(usable_width(pdf), 8, plain(line[2:].strip()), align="L")
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.ln(2)
            pdf.set_font("wqy", size=13)
            pdf.multi_cell(usable_width(pdf), 7, plain(line[3:].strip()), align="L")
            pdf.ln(1)
        elif line.startswith("### "):
            pdf.set_font("wqy", size=11.5)
            pdf.multi_cell(usable_width(pdf), 6, plain(line[4:].strip()), align="L")
            pdf.ln(1)
        elif line.strip():
            write_rich(pdf, line.strip())
        i += 1
    pdf.output(str(pdf_path))
    print(f"wrote {pdf_path} pages={pdf.page_no()}")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        render(Path(sys.argv[1]), Path(sys.argv[2]))
    else:
        render()
