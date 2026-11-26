"""Watch an online catalogue and get an alert when a product is new, removed or changes price.

Alerts go to Telegram or Discord. Before running, set ONE of these:
    TELEGRAM_TOKEN and TELEGRAM_CHAT_ID
    DISCORD_WEBHOOK

Usage:
    python monitor.py --once --dry-run    # one check, print the alerts instead of sending them
    python monitor.py --once              # one check (for cron or Windows Task Scheduler)
    python monitor.py --every 600         # keep checking every 10 minutes

The demo watches the "Mystery" category of books.toscrape.com, a website built for scraping practice.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

WATCH_URL = "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html"
STATE_FILE = Path(__file__).with_name("state.json")
USER_AGENT = "Mozilla/5.0 (compatible; portfolio-monitor/1.0)"
DELAY = 1.0  # seconds between page requests


def fetch_products(url: str) -> dict[str, dict]:
    """Return {product_url: {"title", "price"}} for every page of the listing."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    products = {}
    while url:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        for card in soup.select("article.product_pod"):
            link = card.select_one("h3 a")
            price = card.select_one("p.price_color").get_text(strip=True)
            products[urljoin(url, link["href"])] = {
                "title": link["title"].strip(),
                "price": float(re.sub(r"[^\d.]", "", price)),
            }
        next_link = soup.select_one("li.next a")
        url = urljoin(url, next_link["href"]) if next_link else None
        if url:
            time.sleep(DELAY)
    return products


def compare(old: dict, new: dict) -> list[str]:
    alerts = []
    for url, product in new.items():
        before = old.get(url)
        if before is None:
            alerts.append(f"NEW: {product['title']} at £{product['price']:.2f}\n{url}")
        elif before["price"] != product["price"]:
            change = (product["price"] - before["price"]) / before["price"] * 100
            kind = "PRICE DROP" if change < 0 else "PRICE RISE"
            alerts.append(f"{kind}: {product['title']} £{before['price']:.2f} -> "
                          f"£{product['price']:.2f} ({change:+.0f}%)\n{url}")
    for url, product in old.items():
        if url not in new:
            alerts.append(f"REMOVED: {product['title']}\n{url}")
    return alerts


def send(text: str, dry_run: bool) -> None:
    if dry_run:
        print("  [alert] " + text.replace("\n", "\n          "))
        return
    token, chat_id = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": text[:4000]}, timeout=20).raise_for_status()
    else:
        requests.post(os.environ["DISCORD_WEBHOOK"], json={"content": text[:1900]},
                      timeout=20).raise_for_status()


def check(dry_run: bool) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    current = fetch_products(WATCH_URL)
    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{now}] First run: {len(current)} products saved as the starting point. No alerts.")
        return
    previous = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    alerts = compare(previous, current)
    for alert in alerts:
        send(alert, dry_run)
    STATE_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{now}] Checked {len(current)} products: {len(alerts)} alert(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true", help="check once and exit")
    parser.add_argument("--every", type=int, default=600, help="seconds between checks (default 600)")
    parser.add_argument("--dry-run", action="store_true", help="print alerts instead of sending them")
    args = parser.parse_args()

    has_telegram = os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")
    if not args.dry_run and not has_telegram and not os.getenv("DISCORD_WEBHOOK"):
        sys.exit("No destination set: define TELEGRAM_TOKEN + TELEGRAM_CHAT_ID or DISCORD_WEBHOOK, "
                 "or use --dry-run.")

    while True:
        try:
            check(args.dry_run)
        except requests.RequestException as error:
            print(f"Network error, will retry on the next check: {error}")
        if args.once:
            break
        time.sleep(args.every)
