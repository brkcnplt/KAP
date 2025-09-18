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
TELEGRAM_CHAT_ID2 = os.getenv("TELEGRAM_CHAT_ID2")

CHAT_IDS = [TELEGRAM_CHAT_ID1, TELEGRAM_CHAT_ID2]

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
    """Telegram mesajı gönder"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        response = requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        })
        print(response.status_code, response.text)


# --- KAP API ---
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

# --- Çalıştır ---
init_db()
response = requests.post(url, headers=headers, json=payload)

if response.status_code == 200:
    data = response.json() or []

    #i. bildirime bak → (publish_date[i+1] - publish_date[i]) > 20 dk mı? → evetse i’yi atla
    for idx, item in enumerate(data_sorted):
    disclosure_id = str(item.get("disclosureIndex"))
    if not disclosure_id:
        continue

    # daha önce gönderilmişse pas geç
    if is_disclosure_sent(disclosure_id):
        continue

    stock = item.get("stockCodes") or item.get("relatedStocks") or ""
    if "ISMEN" in stock:
        print("⏭ ISMEN bildirimi atlandı.")
        continue

    if "THYAO" in stock:
        stock = "THYAO"

    title = item.get("summary") or ""
    summary = item.get("subject") or ""
    publish_date = item["publishDate"]
    publish_date_parsed = datetime.strptime(publish_date, "%d.%m.%Y %H:%M:%S")
    link = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_id}"

    # 🔍 Bir SONRAKİ bildirimin publish_date farkını kontrol et
    if idx + 1 < len(data_sorted):
        next_item = data_sorted[idx + 1]
        next_publish_date = datetime.strptime(next_item["publishDate"], "%d.%m.%Y %H:%M:%S")

        if (next_publish_date - publish_date_parsed).total_seconds() > 20 * 60:
            print(f"⏭ {disclosure_id} bildirimi sonraki ile arasında >20 dk olduğu için atlandı.")
            continue

    # Eğer atlanmadıysa gönder
    message = (
        f"📢 {stock}\n\n"
        f"🔹 {title}\n\n"
        f"📄 {summary}\n\n"
        f"🕒 {publish_date}\n\n"
        f"🔗 <a href='{link}'>Bildirimi Görüntüle</a>\n\n"
    )

    send_telegram(message)
    save_disclosure(disclosure_id, publish_date, stock, title, summary)


else:
    send_telegram(f"KAP verisi alınamadı! Status Code: {response.status_code}")
