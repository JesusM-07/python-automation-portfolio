"""Find your Telegram chat id and send a test alert through monitor.py.

1. In Telegram, open @BotFather, send /newbot and copy the token it gives you.
2. Open your new bot, press Start (or send it any message).
3. Run:  python telegram_setup.py
   It asks for the token without showing it on screen. Never paste the token in a file or a chat.
"""
import getpass
import os
import sys

import requests

import monitor


def bot_username(token: str) -> str:
    response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=20)
    if response.status_code in (401, 404):
        sys.exit("Telegram rejected the token. Copy it again from @BotFather (the whole line).")
    response.raise_for_status()
    return response.json()["result"]["username"]


def find_chats(token: str) -> dict[int, str]:
    response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20)
    if response.status_code == 409:
        sys.exit("This bot has a webhook set, so its messages go elsewhere. Remove it with "
                 f"https://api.telegram.org/bot<token>/deleteWebhook and run this again.")
    response.raise_for_status()
    updates = response.json()["result"]
    info = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=20).json()["result"]
    print(f"Telegram has {len(updates)} update(s) for this bot "
          f"(pending: {info.get('pending_update_count', 0)}, webhook: {'yes' if info.get('url') else 'no'})")
    chats = {}
    for update in updates:
        message = update.get("message") or update.get("edited_message") or update.get("channel_post")
        if message:
            chat = message["chat"]
            chats[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    return chats


def ask_token() -> str:
    prompt = "Paste the bot token and press Enter: "
    try:
        return getpass.getpass(prompt, echo_char="*").strip()  # shows **** (Python 3.14+)
    except TypeError:  # older Python: the token stays fully hidden
        return getpass.getpass(prompt + "(nothing will show while you paste) ").strip()


if __name__ == "__main__":
    token = os.getenv("TELEGRAM_TOKEN") or ask_token()
    username = bot_username(token)
    print(f"Token OK: this token belongs to @{username}")
    chats = find_chats(token)
    if not chats:
        sys.exit(f"No messages yet. Open https://t.me/{username} in Telegram, press Start (or send it any "
                 "message), then run this again.")
    chat_id = list(chats)[-1]
    print(f"Chat id found: {chat_id} ({chats[chat_id]})")

    # Send a sample alert with the same function the monitor uses.
    os.environ["TELEGRAM_TOKEN"], os.environ["TELEGRAM_CHAT_ID"] = token, str(chat_id)
    sample = monitor.compare(
        {"https://books.toscrape.com/catalogue/the-past-never-ends_942/index.html":
            {"title": "The Past Never Ends", "price": 64.50}},
        {"https://books.toscrape.com/catalogue/the-past-never-ends_942/index.html":
            {"title": "The Past Never Ends", "price": 56.50}},
    )
    for alert in sample:
        monitor.send("TEST ALERT (sample data)\n" + alert, dry_run=False)
    print("Test alert sent. Check your Telegram.")
    print("\nTo run the monitor with real alerts, set these two variables first:")
    print(f'  Linux/macOS:  export TELEGRAM_CHAT_ID="{chat_id}"  and  export TELEGRAM_TOKEN="<your token>"')
    print(f'  Windows:      $env:TELEGRAM_CHAT_ID="{chat_id}"  and  $env:TELEGRAM_TOKEN="<your token>"')
