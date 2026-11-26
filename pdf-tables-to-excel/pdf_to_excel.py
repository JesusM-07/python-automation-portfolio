"""Extract the tables of a PDF (every page) into one clean Excel sheet.

Usage:
    python pdf_to_excel.py input.pdf [output.xlsx]

Works with PDFs that contain real text (you can select it). Scanned PDFs need OCR first.
"""
import re
import sys
from pathlib import Path

import pymupdf
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

NUMBER = re.compile(r"^-?[£$€]?\s?-?\d[\d,]*(\.\d+)?\s?[£$€]?$")


# Words as the PDF stores them, with ligatures such as "ﬀ" expanded back to "ff".
WORD_FLAGS = pymupdf.TEXTFLAGS_WORDS & ~pymupdf.TEXT_PRESERVE_LIGATURES


def table_rows(page: pymupdf.Page, table) -> list[list[str]]:
    """Put each word in the cell that contains its centre.

    This keeps spaces and decimal points in place (the generic table.extract() can lose them)
    and never copies a word into two rows when the table has very thin rows.
    """
    words = page.get_text("words", flags=WORD_FLAGS)
    rows = []
    for row in table.rows:
        cells = []
        for bbox in row.cells:
            if bbox is None:  # merged cell
                cells.append("")
                continue
            box = pymupdf.Rect(bbox)
            inside = [w for w in words if box.contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))]
            inside.sort(key=lambda w: (w[5], w[6], w[7]))  # block, line, word: reading order
            cells.append(" ".join(w[4] for w in inside))
        rows.append(cells)
    return rows


def extract(pdf_path: Path) -> tuple[list[str], list[list[str]]]:
    header, rows = None, []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            found = 0
            for table in page.find_tables().tables:
                data = table_rows(page, table)
                if header is None:
                    header, data = data[0], data[1:]
                elif data and data[0] == header:  # header repeated on a new page
                    data = data[1:]
                data = [row for row in data if any(row)]
                rows.extend(data)
                found += len(data)
            print(f"Page {page.number + 1}: {found} rows")
    if header is None:
        sys.exit("No tables found. If the PDF is scanned, it needs OCR first.")
    return header, rows


def to_number(text: str) -> float | int:
    value = float(re.sub(r"[^\d.\-]", "", text))
    return int(value) if value.is_integer() and "." not in text else value


def numeric_columns(rows: list[list[str]]) -> set[int]:
    """A column is numeric only if every non-empty value in it looks like a number."""
    numeric = set()
    for col in range(len(rows[0])):
        values = [row[col] for row in rows if row[col]]
        if values and all(NUMBER.match(v) for v in values):
            numeric.add(col)
    return numeric


def save(header: list[str], rows: list[list[str]], out: Path) -> None:
    numeric = numeric_columns(rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for row in rows:
        ws.append([to_number(v) if i in numeric and v else v for i, v in enumerate(row)])
    for i in numeric:  # keep the currency symbol as a cell format, the value stays a number
        symbol = next((s for s in "£$€" if any(s in row[i] for row in rows)), None)
        if symbol:
            for cell in list(ws.columns)[i][1:]:
                cell.number_format = f'"{symbol}"#,##0.00'
    for col_cells in ws.columns:
        longest = max(len(str(c.value or "")) for c in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(60, longest + 2)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(out)


if __name__ == "__main__":
    pdf = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else pdf.with_suffix(".xlsx")
    header, rows = extract(pdf)
    save(header, rows, out)
    empty = sum(1 for row in rows for v in row if not v)
    print(f"\n{len(rows)} rows x {len(header)} columns saved to {out}")
    print(f"Empty cells: {empty}")
