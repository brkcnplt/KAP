import requests
from datetime import date
import os

# --- Telegram ayarları ---
#TOKEN = "8153163023:AAF6TyciGLkjCmr8oXq1hQEO50ahMsGpRmA"
#CHAT_ID = "1642459289"

# --- Telegram ayarları ---
# GitHub Actions'ta secrets kullan
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8153163023:AAF6TyciGLkjCmr8oXq1hQEO50ahMsGpRmA")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1642459289")

def send_telegram(message):
    """Telegram mesajı gönder"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})

# --- Son kayıt sayısını dosyada tut ---
def get_last_count():
    if os.path.exists("last_count.txt"):
        with open("last_count.txt", "r") as f:
            return int(f.read().strip() or 0)
    return 0

def set_last_count(count):
    with open("last_count.txt", "w") as f:
        f.write(str(count))

# --- KAP verisi çekme ---
today = date.today().strftime("%Y-%m-%d")
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

response = requests.post(url, headers=headers, json=payload)

# --- Gelen veriyi işleme ---
if response.status_code == 200:
    data = response.json() or []
    new_count = len(data)
    last_count = get_last_count()
    print(f"Yeni KAP bildirimi sayısı: {new_count}, Son kayıtlı bildirim sayısı: {last_count}")

    if new_count == 0:
        send_telegram("Bugün için yeni KAP bildirimi yok ✅")
    elif new_count > last_count:
        # sadece yeni gelenleri gönder
        new_items = data[:new_count - last_count]
        for item in new_items:
            stock = item.get("stockCodes") or item.get("relatedStocks") or ""
            title = item.get("summary") or ""
            summary = item.get("subject") or ""
            message = f"📢 {stock}\n🔹 {title}\n📄 {summary}"
            send_telegram(message)

        # sayıyı güncelle
        set_last_count(new_count)
    else:
        # hiç değişiklik yok
 message = f"📢 değişiklik yok"
            send_telegram(message)
        print("Yeni bildirim yok, telegrama mesaj gönderilmedi.")
else:
    send_telegram(f"KAP verisi alınamadı! Status Code: {response.status_code}")
