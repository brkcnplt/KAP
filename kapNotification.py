import requests
from datetime import date, datetime
import os
import sqlite3
from dotenv import load_dotenv 

# --- Telegram ayarları ---
load_dotenv()  # .env dosyasını yükler

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Lütfen 'TELEGRAM_TOKEN' environment variable'ını ayarlayın!")

TELEGRAM_CHAT_ID1 = os.getenv("TELEGRAM_CHAT_ID1")
if not TELEGRAM_CHAT_ID1:
    raise ValueError("Lütfen 'TELEGRAM_CHAT_ID1' environment variable'ını ayarlayın!")

TELEGRAM_CHAT_ID2 = os.getenv("TELEGRAM_CHAT_ID2")
if not TELEGRAM_CHAT_ID2:
    raise ValueError("Lütfen 'TELEGRAM_CHAT_ID2' environment variable'ını ayarlayın!")

CHAT_IDS = [TELEGRAM_CHAT_ID1, TELEGRAM_CHAT_ID2]

today = date.today().strftime("%Y-%m-%d")

def send_telegram(message: str):
    """Telegram mesajı gönder"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        response = requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
        print(response.status_code, response.text)

# --- DB bağlantısı ---
DB_FILE = "kap_records.db"

def init_db():
    """Tabloları oluştur (yoksa)"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Gönderilmiş bildirimler
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sent_disclosures (
            disclosure_id TEXT PRIMARY KEY,
            stock_code TEXT,
            publish_date TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_sent(disclosure_id: str) -> bool:
    """Bu bildirim daha önce gönderilmiş mi?"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sent_disclosures WHERE disclosure_id = ?", (disclosure_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def mark_as_sent(disclosure_id: str, stock_code: str, publish_date: str):
    """Bildirimi DB'ye ekle (gönderildi olarak işaretle)"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO sent_disclosures (disclosure_id, stock_code, publish_date)
        VALUES (?, ?, ?)
    """, (disclosure_id, stock_code, publish_date))
    conn.commit()
    conn.close()


# --- KAP verisi çekme ---
url = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"

payload = {
    "fromDate": today,
    "toDate": today,
    "memberType": "IGS",
    "mkkMemberOidList": [
        "4028e4a140f2ed720140f3790d6a01ad",
        "4028e4a140f2ed71014106890fae0138",
        "4028e4a140f2ed710140f328bed700a5",
        "4028e4a240e8d16e0140e951bf04007b",
        "8acae2c57d3bf002017e016f30e442c6",
        "4028e4a240f2ef470141175e189f0453",
        "4028e4a140f2ed720140f37f139c01bc",
        "4028e4a2422d9a78014232e751bc22a4",
        "4028e4a140f2ed720140f376bebb01a7",
        "4028e4a240f2ef4701413a5c97b805ea",
        "4028e4a140ee84900140f1f1584c0015",
        "4028e4a140f275530140f277aa100008",
        "8acae2c562329bd10164405fe6c17996",
        "4028e4a1415f4d9b0141603cd3904103"
    ],
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

# DB hazırla
init_db()

response = requests.post(url, headers=headers, json=payload)

# --- Gelen veriyi işleme ---
if response.status_code == 200:
    data = response.json() or []

    for item in data:
        disclosure_id = str(item.get("disclosureIndex"))
        if not disclosure_id:
            continue

        # Daha önce gönderilmiş mi kontrol et
        if is_sent(disclosure_id):
            print(f"⏭ Bildirim zaten gönderilmiş: {disclosure_id}")
            continue

        stock = item.get("stockCodes") or item.get("relatedStocks") or ""
        stockCode = stock[:5]

        # 🚨 ISMEN için mesaj gönderme
        if "ISMEN" in stock:
            print("⏭ ISMEN bildirimi atlandı.")
            mark_as_sent(disclosure_id, stockCode, item["publishDate"])
            continue

        if "THYAO" in stock:
            stockCode = "THYAO"

        title = item.get("summary") or ""
        summary = item.get("subject") or ""
        link = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_id}"

        message = (
            f"📢 {stock}\n\n"
            f"🔹 {title}\n\n" 
            f"📄 {summary} \n\n"
            f"🕒 {item['publishDate']}\n\n"
            f"🔗 <a href='{link}'>Bildirimi Görüntüle</a> \n\n"
        )

        print(f"📤 Yeni bildirim gönderiliyor: {disclosure_id}")
        send_telegram(message)

        # DB'ye kaydet
        mark_as_sent(disclosure_id, stockCode, item["publishDate"])

else:
    send_telegram(f"KAP verisi alınamadı! Status Code: {response.status_code}")
