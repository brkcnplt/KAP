import requests
from datetime import date, datetime , timedelta
import os
import sqlite3
from collections import OrderedDict
from contextlib import contextmanager
from typing import IO, Dict, Iterable, Iterator, Mapping, Optional, Tuple, Union
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



def send_telegram(message):
    """Telegram mesajı gönder"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
        print(response.status_code, response.text)

# --- DB bağlantısı ---
DB_FILE = "kap_records.db"

def init_db():
    """Tabloyu oluştur (yoksa)"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kap_counts (
            record_date TEXT PRIMARY KEY,
            count INTEGER
        )
    """)
    conn.commit()
    conn.close()

def clear_db():
    """DB'deki tüm kayıtları sil"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM kap_counts")
    conn.commit()
    conn.close()
    print("✅ DB'deki tüm kayıtlar silindi.")

def get_db_count():
    """Bugün için kayıtlı KAP sayısını getir"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT count FROM kap_counts WHERE record_date = ?", (today,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

def set_db_count(count):
    """Bugün için KAP sayısını kaydet/güncelle"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO kap_counts (record_date, count)
        VALUES (?, ?)
        ON CONFLICT(record_date) DO UPDATE SET count = excluded.count
    """, (today, count))
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
#clear_db()  # test amaçlı DB'yi temizle
init_db()  # tabloyu hazırla
response = requests.post(url, headers=headers, json=payload)

# --- Gelen veriyi işleme ---
if response.status_code == 200:
    data = response.json() or []
    new_count = len(data)
    last_count = get_db_count()
    print(f"Yeni KAP bildirimi sayısı: {new_count}, DB'deki sayı: {last_count}")

    if new_count == last_count:
        print("Bugün için aynı sayıda kayıt var, işlem yapılmadı ✅")
    elif new_count > last_count:
        # publishDate'e göre sırala
        for item in data:
            item["publishDateParsed"] = datetime.strptime(item["publishDate"], "%d.%m.%Y %H:%M:%S")
        data_sorted = sorted(data, key=lambda x: x["publishDateParsed"])

        diff = new_count - last_count
        new_items_sorted = data_sorted[-diff:]

        for item in new_items_sorted:
            stock = item.get("stockCodes") or item.get("relatedStocks") or ""
            stockCode = stock[:5]
            # 🚨 ISMEN için mesaj gönderme
            if "ISMEN" in stock:
                print("⏭ ISMEN bildirimi atlandı.")
                continue

            if "THYAO" in stock:
                stockCode = "THYAO"

            title = item.get("summary") or ""
            summary = item.get("subject") or ""
            bildirimNo = item.get("disclosureIndex") or ""
            link = f"https://www.kap.org.tr/tr/Bildirim/{bildirimNo}"

            message = (
                f"📢 {stock}\n\n"
                f"🔹 {title}\n\n" 
                f"📄 {summary} \n\n"
                f"🕒 {item['publishDate']}\n\n"
                f"🔗 <a href='{link}'>Bildirimi Görüntüle</a> \n\n"

            
            )
            print(message)
            send_telegram(message)

        # DB güncelle
        set_db_count(new_count)
    else:
        print("DB'deki sayı API'den büyük görünüyor (tutarsızlık).")

else:
    send_telegram(f"KAP verisi alınamadı! Status Code: {response.status_code}")
