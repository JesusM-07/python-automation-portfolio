"""Build the sample PDF used in this demo: a multi-page price list.

The data comes from books.toscrape.com (a practice website), scraped by ../books-to-excel.
Usage:
    python make_sample_pdf.py ../books-to-excel/books.csv sample_price_list.pdf [rows]
"""
import csv
import html
import sys

import pymupdf

CSS = """
* { font-family: sans-serif; }
h1 { font-size: 16px; margin-bottom: 4px; }
p { font-size: 9px; color: #555555; margin-bottom: 10px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #444444; font-size: 9px; padding: 3px; }
th { background-color: #DDDDDD; text-align: left; }
"""


def build_html(rows: list[dict]) -> str:
    lines = [
        "<h1>Price list (sample)</h1>",
        "<p>Sample document for a PDF-to-Excel demo. Data: books.toscrape.com, a practice website.</p>",
        "<table><tr><th>Title</th><th>Price</th><th>Rating</th><th>In stock</th></tr>",
    ]
    for row in rows:
        lines.append(
            f"<tr><td>{html.escape(row['Title'])}</td><td>£{float(row['Price (GBP)']):.2f}</td>"
            f"<td>{row['Rating (1-5)']}</td><td>{row['In stock']}</td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


if __name__ == "__main__":
    source, target = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 150
    with open(source, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))[:limit]

    story = pymupdf.Story(html=build_html(rows), user_css=CSS)
    writer = pymupdf.DocumentWriter(target)
    page_rect = pymupdf.paper_rect("a4")
    content_area = page_rect + (40, 40, -40, -40)
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_area)
        story.draw(device)
        writer.end_page()
    writer.close()
    print(f"{len(rows)} rows written to {target}")
