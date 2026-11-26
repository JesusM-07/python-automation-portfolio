"""Scrape every book from books.toscrape.com into a formatted Excel file (and a CSV).

Usage:
    python scrape_books.py [output_name]

books.toscrape.com is a website built for scraping practice.
"""
import csv
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
USER_AGENT = "Mozilla/5.0 (compatible; portfolio-scraper/1.0)"
DELAY = 1.0  # seconds between requests, to be polite to the server
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def robots_allows(url: str) -> bool:
    rp = urllib.robotparser.RobotFileParser(urljoin(url, "/robots.txt"))
    try:
        rp.read()
    except OSError:
        return True
    return rp.can_fetch(USER_AGENT, url)


def parse_page(soup: BeautifulSoup, page_url: str) -> list[dict]:
    books = []
    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        price = card.select_one("p.price_color").get_text(strip=True)
        rating = card.select_one("p.star-rating")["class"][-1]
        stock = card.select_one("p.availability").get_text(strip=True)
        books.append({
            "Title": link["title"].strip(),
            "Price (GBP)": float(re.sub(r"[^\d.]", "", price)),
            "Rating (1-5)": RATINGS.get(rating),
            "In stock": "Yes" if "In stock" in stock else "No",
            "URL": urljoin(page_url, link["href"]),
        })
    return books


def scrape() -> tuple[list[dict], int | None]:
    if not robots_allows(START_URL):
        sys.exit("robots.txt does not allow scraping this site. Stopping.")
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    url, books, expected, page = START_URL, [], None, 0
    while url:
        page += 1
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        if expected is None:  # the site shows the total number of results on page 1
            total = soup.select_one("form.form-horizontal strong")
            expected = int(total.get_text()) if total else None
        page_books = parse_page(soup, url)
        books.extend(page_books)
        print(f"Page {page}: {len(page_books)} books")
        next_link = soup.select_one("li.next a")
        url = urljoin(url, next_link["href"]) if next_link else None
        if url:
            time.sleep(DELAY)
    return books, expected


def save(rows: list[dict], name: str) -> None:
    with open(f"{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    wb = Workbook()
    ws = wb.active
    ws.title = "Books"
    ws.append(list(rows[0].keys()))
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for row in rows:
        ws.append(list(row.values()))
    for cell in ws["B"][1:]:
        cell.number_format = '"£"#,##0.00'
    for column, width in zip("ABCDE", (60, 13, 13, 10, 70)):
        ws.column_dimensions[column].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(f"{name}.xlsx")


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "books"
    books, expected = scrape()
    if not books:
        sys.exit("No books found.")
    save(books, output)
    print(f"\n{len(books)} books saved to {output}.xlsx and {output}.csv")
    if expected is not None:
        status = "OK" if len(books) == expected else "MISMATCH, review"
        print(f"Check: the site lists {expected} books, the file has {len(books)} -> {status}")
    empty = sum(1 for b in books for v in b.values() if v in ("", None))
    print(f"Empty fields: {empty}")
