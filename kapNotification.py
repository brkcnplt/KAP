#!/usr/bin/env python3
import requests
from datetime import date, datetime
import os
import sqlite3
from dotenv import load_dotenv
import json

# --- Telegram ayarları ---
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Lütfen 'TELEGRAM_TOKEN' environment variable'ını ayarlayın!")

TELEGRAM_CHAT_ID1 = os.getenv("TELEGRAM_CHAT_ID1")
TELEGRAM_CHAT_ID2 = os.getenv("TELEGRAM_CHAT_ID2")

CHAT_IDS = [c for c in (TELEGRAM_CHAT_ID1, TELEGRAM_CHAT_ID2) if c]

today = date.today().strftime("%Y-%m-%d")
DB_FILE = "kap_records.db"

# --- DB Fonksiyonları ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kap_records (
            disclosure_id TEXT PRIMARY KEY,
            publish_date TEXT,
            stock TEXT,
            title TEXT,
            summary TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_disclosure_sent(disclosure_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM kap_records WHERE disclosure_id = ?", (disclosure_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def save_disclosure(disclosure_id, publish_date, stock, title, summary):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO kap_records (disclosure_id, publish_date, stock, title, summary)
        VALUES (?, ?, ?, ?, ?)
    """, (disclosure_id, publish_date, stock, title, summary))
    conn.commit()
    conn.close()

# --- Telegram ---
def send_telegram(message):
    if not CHAT_IDS:
        print("Uyarı: Telegram chat ID bulunmuyor, mesaj gönderilemiyor.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        try:
            response = requests.post(url, data={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }, timeout=15)
            print(f"Telegram -> {chat_id}: {response.status_code}")
        except Exception as e:
            print(f"Telegram gönderim hatası ({chat_id}): {e}")

# --- KAP API ---
def fetch_disclosures():
    url = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
    payload = {
        "fromDate": today,
        "toDate": today,
        "memberType": "IGS",
        "mkkMemberOidList": [],
        "inactiveMkkMemberOidList": [],
        "disclosureClass": "",
        "subjectList": [],
        "isLate": "",
        "mainSector": "",
        "sector": "",
        "subSector": "",
        "marketOid": "",
        "index": "",
        "bdkReview": "",
        "bdkMemberOidList": [],
        "year": "",
        "term": "",
        "ruleType": "",
        "period": "",
        "fromSrc": False,
        "srcCategory": "",
        "disclosureIndexList": []
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            print("KAP isteği başarısız:", resp.status_code, resp.text[:500])
            return {}
    except Exception as e:
        print("KAP API hatası:", e)
        return {}

def main():
    init_db()
    raw = fetch_disclosures()

    # Listeyi yakala
    items = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if "data" in raw and isinstance(raw["data"], list):
            items = raw["data"]
        elif "items" in raw and isinstance(raw["items"], list):
            items = raw["items"]
        else:
            for v in raw.values():
                if isinstance(v, list):
                    items = v
                    break

    if not items:
        print("Bildirim yok.")
        return

    # publishDate'e göre sırala
    def parse_publish(item):
        pd = item.get("publishDate") or item.get("publish_date") or ""
        try:
            return datetime.strptime(pd, "%d.%m.%Y %H:%M:%S")
        except Exception:
            return datetime.min

    data_sorted = sorted(items, key=parse_publish)

    # sadece en son bildirimi al
    last_item = data_sorted[-1]

    disclosure_id = str(last_item.get("disclosureIndex") or last_item.get("id") or "").strip()
    if not disclosure_id:
        print("Uyarı: disclosure_id yok.")
        return

    # --- En kritik kısım: Daha önce gönderildiyse çık ---
    if is_disclosure_sent(disclosure_id):
        print("Yeni bildirim yok.")
        return

    # Stock normalizasyon
    stock_field = last_item.get("stockCodes") or last_item.get("relatedStocks") or last_item.get("stock") or ""
    if isinstance(stock_field, list):
        stock_str = ",".join(stock_field)
    else:
        stock_str = str(stock_field)

    if "ISMEN" in stock_str:
        print(f"⏭ {disclosure_id} (ISMEN) bildirimi atlandı.")
        save_disclosure(disclosure_id, last_item.get("publishDate", ""), stock_str, "", "")
        return

    if "THYAO" in stock_str.upper():
        stock_str = "THYAO"

    title = last_item.get("title") or last_item.get("summary") or last_item.get("subject") or ""
    summary = last_item.get("summary") or last_item.get("subject") or ""
    publish_date = last_item.get("publishDate") or ""
    link = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_id}"

    message = (
        f"📢 {stock_str}\n\n"
        f"🔹 {title}\n\n"
        f"📄 {summary}\n\n"
        f"🕒 {publish_date}\n\n"
        f"🔗 <a href='{link}'>Bildirimi Görüntüle</a>\n\n"
    )

    send_telegram(message)
    save_disclosure(disclosure_id, publish_date, stock_str, title, summary)
    print(f"Gönderildi ve kaydedildi: {disclosure_id}")

if __name__ == "__main__":
    main()
