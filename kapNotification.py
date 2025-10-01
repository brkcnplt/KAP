#!/usr/bin/env python3
import requests
from datetime import date, datetime
import os
import sqlite3
from dotenv import load_dotenv
import json
import logging
import traceback

# --- Logging ayarı ---
LOG_FILE = "kap_debug.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),  # GitHub Actions / terminal için
        logging.FileHandler(LOG_FILE, encoding="utf-8")  # ayrıca dosyaya da yaz
    ]
)
logger = logging.getLogger(__name__)

# --- Telegram ayarları ---
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("Lütfen 'TELEGRAM_TOKEN' environment variable'ını ayarlayın!")
    raise ValueError("Lütfen 'TELEGRAM_TOKEN' environment variable'ını ayarlayın!")

TELEGRAM_CHAT_ID1 = os.getenv("TELEGRAM_CHAT_ID1")
TELEGRAM_CHAT_ID2 = os.getenv("TELEGRAM_CHAT_ID2")

CHAT_IDS = [c for c in (TELEGRAM_CHAT_ID1, TELEGRAM_CHAT_ID2) if c] if False else [c for c in (TELEGRAM_CHAT_ID1, TELEGRAM_CHAT_ID2) if c]  # safety fallback

today = date.today().strftime("%Y-%m-%d")
DB_FILE = "kap_records.db"

logger.info("Başlatılıyor. Tarih: %s, DB dosyası: %s", today, DB_FILE)
logger.info("CHAT_IDS: %s", CHAT_IDS or "(yok)")

# --- DB Fonksiyonları ---
def init_db():
    try:
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
        logger.info("DB initialized / tablo kontrol edildi.")
    except Exception as e:
        logger.exception("DB init hatası: %s", e)
        raise

def is_disclosure_sent(disclosure_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM kap_records WHERE disclosure_id = ?", (disclosure_id,))
        row = cur.fetchone()
        conn.close()
        found = row is not None
        logger.debug("is_disclosure_sent(%s) -> %s", disclosure_id, found)
        return found
    except Exception as e:
        logger.exception("is_disclosure_sent hatası: %s", e)
        return False

def save_disclosure(disclosure_id, publish_date, stock, title, summary):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO kap_records (disclosure_id, publish_date, stock, title, summary)
            VALUES (?, ?, ?, ?, ?)
        """, (disclosure_id, publish_date, stock, title, summary))
        conn.commit()
        conn.close()
        logger.info("DB'ye kaydedildi: %s", disclosure_id)
    except Exception as e:
        logger.exception("save_disclosure hatası: %s", e)

# --- Telegram ---
def send_telegram(message):
    if not CHAT_IDS:
        logger.warning("Telegram chat ID bulunmuyor, mesaj gönderilemiyor.")
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
            logger.info("Telegram -> %s : status=%s, payload_len=%d", chat_id, response.status_code, len(message))
            # hata durumunda response.text'i logla (kısa)
            if response.status_code != 200:
                logger.warning("Telegram response text (truncated): %s", response.text[:500])
        except Exception as e:
            logger.exception("Telegram gönderim hatası (%s): %s", chat_id, e)

# --- KAP API ---
def fetch_disclosures():
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
    logger.info("KAP API'ye istek atılıyor (fromDate=%s toDate=%s)...", today, today)
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        logger.info("KAP response status: %s", resp.status_code)
        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception:
                logger.exception("KAP JSON parse hatası, text (truncated): %s", resp.text[:1000])
                return {}
        else:
            logger.warning("KAP isteği başarısız: %s", resp.status_code)
            logger.debug("Response text (truncated): %s", resp.text[:500])
            return {}
    except Exception as e:
        logger.exception("KAP API hatası: %s", e)
        return {}

def extract_disclosure_id(item):
    """Daha güvenli disclosure_id çıkarma (farklı alanlara bak)"""
    return str(
        item.get("disclosureIndex")
        or item.get("disclosure_id")
        or item.get("id")
        or item.get("disclosureNo")
        or item.get("referenceNo")
        or ""
    ).strip()

def main():
    logger.info("Run started.")
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

    logger.info("API'den alınan öğe sayısı: %d", len(items))
    if not items:
        logger.info("Bildirim yok, çıkılıyor.")
        return

    # publishDate'e göre sırala
    def parse_publish(item):
        pd = item.get("publishDate") or item.get("publish_date") or ""
        try:
            return datetime.strptime(pd, "%d.%m.%Y %H:%M:%S")
        except Exception:
            return datetime.min

    try:
        data_sorted = sorted(items, key=parse_publish)
    except Exception as e:
        logger.exception("Sıralama hatası: %s", e)
        data_sorted = items

    # sadece en son bildirimi al
    last_item = data_sorted[-1]
    logger.info("En son item keys: %s", list(last_item.keys()))

    disclosure_id = extract_disclosure_id(last_item)
    logger.info("Çekilen disclosure_id: %s", disclosure_id)

    if not disclosure_id:
        logger.warning("disclosure_id bulunamadı, atlanıyor.")
        return

    # --- Daha önce gönderildiyse çık ---
    if is_disclosure_sent(disclosure_id):
        logger.info("disclosure_id zaten DB'de (%s). Yeni bildirim yok.", disclosure_id)
        return
    else:
        logger.info("disclosure_id DB'de yok, işlem yapılacak: %s", disclosure_id)

    # Stock normalizasyon
    stock_field = last_item.get("stockCodes") or last_item.get("relatedStocks") or last_item.get("stock") or ""
    if isinstance(stock_field, list):
        stock_str = ",".join(stock_field)
    else:
        stock_str = str(stock_field)
    logger.info("Raw stock field: %s", stock_str[:200])

    # ISMEN atla (ve yine kaydet)
    if "ISMEN" in stock_str:
        logger.info("ISMEN bildirimi tespit edildi, mesaj gönderilmiyor. disclosure_id kaydediliyor.")
        save_disclosure(disclosure_id, last_item.get("publishDate", ""), stock_str, "", "")
        return

    # THYAO fix
    if "THYAO" in stock_str.upper():
        stock_str = "THYAO"
        logger.info("THYAO tespit edildi, stock_str düzeltildi.")

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

    logger.info("Telegram mesajı gönderiliyor (kısaltılmış): %s", message[:250].replace("\n", " | "))
    try:
        send_telegram(message)
    except Exception as e:
        logger.exception("send_telegram çağrısı sırasında hata: %s", e)

    # DB'ye kaydet
    try:
        save_disclosure(disclosure_id, publish_date, stock_str, title, summary)
        logger.info("Bildirim gönderildi ve DB'ye kaydedildi: %s", disclosure_id)
    except Exception:
        logger.exception("save_disclosure sırasında hata:\n%s", traceback.format_exc())

if __name__ == "__main__":
    main()
