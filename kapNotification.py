#!/usr/bin/env python3
import requests
from datetime import date, datetime
import os
import sqlite3
from dotenv import load_dotenv
import json

# --- Telegram ayarları ---
load_dotenv()  # .env dosyasını yükler

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Lütfen 'TELEGRAM_TOKEN' environment variable'ını ayarlayın!")

TELEGRAM_CHAT_ID1 = os.getenv("TELEGRAM_CHAT_ID1")
TELEGRAM_CHAT_ID2 = os.getenv("TELEGRAM_CHAT_ID2")

# boş/None chat id'leri atla
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
    """Telegram mesajı gönder (CHAT_IDS içinde None varsa atlanır)"""
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
            # isteğe bağlı olarak response.text yazdırılabilir:
            # print(response.text)
        except Exception as e:
            print(f"Telegram gönderim hatası ({chat_id}): {e}")

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
response = requests.post(url, headers=headers, json=payload, timeout=30)

if response.status_code == 200:
    raw = response.json() or {}

    # API cevap formatına göre listeyi tespit et
    items = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        # yaygın alan isimlerini dene
        if "data" in raw and isinstance(raw["data"], list):
            items = raw["data"]
        elif "items" in raw and isinstance(raw["items"], list):
            items = raw["items"]
        else:
            # dict içinde ilk list değerini al
            for v in raw.values():
                if isinstance(v, list):
                    items = v
                    break

    if not items:
        print("KAP'dan dönen veri içinde bildirim listesi bulunamadı. Response örneği:")
        print(json.dumps(raw, indent=2, ensure_ascii=False)[:2000])
    else:
        # publishDate parse fonksiyonu
        def parse_publish(item):
            pd = item.get("publishDate") or item.get("publish_date") or ""
            try:
                return datetime.strptime(pd, "%d.%m.%Y %H:%M:%S")
            except Exception:
                return datetime.min

        # kronolojik sıraya koy (eski -> yeni)
        data_sorted = sorted(items, key=parse_publish)

        for idx, item in enumerate(data_sorted):
            # -- gerekli alanlar --
            disclosure_id = str(item.get("disclosureIndex") or item.get("disclosure_id") or item.get("id") or "").strip()
            if not disclosure_id:
                print(f"[{idx}] Uyarı: disclosure_id yok, atlanıyor.")
                continue

            # daha önce gönderilmişse pas geç
            if is_disclosure_sent(disclosure_id):
                # print(f"{disclosure_id} daha önce gönderilmiş.")
                continue

            # stock field'larını normalize et
            stock_field = item.get("stockCodes") or item.get("relatedStocks") or item.get("stock") or ""
            if isinstance(stock_field, list):
                stock_str = ",".join(stock_field)
            else:
                stock_str = str(stock_field)

            # ISMEN bildirimi atlamak istemişsin
            if "ISMEN" in stock_str:
                print(f"⏭ {disclosure_id} (ISMEN) bildirimi atlandı.")
                continue

            # THY kodu düzeltmesi
            if "THYAO" in stock_str or "THYAO" in stock_str.upper():
                stock_str = "THYAO"

            # başlık/özet
            title = item.get("title") or item.get("summary") or item.get("subject") or ""
            summary = item.get("summary") or item.get("subject") or ""

            publish_date = item.get("publishDate") or ""
            try:
                publish_date_parsed = datetime.strptime(publish_date, "%d.%m.%Y %H:%M:%S")
            except Exception:
                publish_date_parsed = None

            link = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_id}"

            # 🔍 Bir SONRAKİ bildirimin publish_date farkını kontrol et (kronolojik sırada next daha yenidir)
            if idx + 1 < len(data_sorted) and publish_date_parsed:
                next_item = data_sorted[idx + 1]
                next_publish_raw = next_item.get("publishDate") or ""
                try:
                    next_publish_date = datetime.strptime(next_publish_raw, "%d.%m.%Y %H:%M:%S")
                    # eğer sonraki bildirimle aradaki fark > 20 dk ise atla
                    if (next_publish_date - publish_date_parsed).total_seconds() > 20 * 60:
                        print(f"⏭ {disclosure_id} bildirimi sonraki ile arasında >20 dk olduğu için atlandı.")
                        continue
                except Exception:
                    # parse hatası olursa devam et
                    pass

            # Gönderilecek mesajı hazırla
            message = (
                f"📢 {stock_str}\n\n"
                f"🔹 {title}\n\n"
                f"📄 {summary}\n\n"
                f"🕒 {publish_date}\n\n"
                f"🔗 <a href='{link}'>Bildirimi Görüntüle</a>\n\n"
            )

            # gönder ve kaydet
            send_telegram(message)
            save_disclosure(disclosure_id, publish_date, stock_str, title, summary)
            print(f"Gönderildi ve kaydedildi: {disclosure_id}")

else:
    send_telegram(f"KAP verisi alınamadı! Status Code: {response.status_code}")
    print("KAP isteği başarısız. Status:", response.status_code, response.text[:1000])
