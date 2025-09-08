import requests
from datetime import date, datetime
import os
import yfinance as yf

# --- Telegram ayarları ---
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8153163023:AAF6TyciGLkjCmr8oXq1hQEO50ahMsGpRmA")
CHAT_IDS = [
    os.environ.get("TELEGRAM_CHAT_ID", "1642459289"),
    "851287347",   # ikinci chat_id
]

today = date.today().strftime("%Y-%m-%d")


def send_telegram(message):
    """Telegram mesajı gönder"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})

# --- Son kayıt sayısını dosyada tut ---
def get_last_count():
    """Dosyadan son kayıtlı sayıyı oku, eğer gün değiştiyse sıfırla"""
    if os.path.exists("last_count.txt"):
        with open("last_count.txt", "r") as f:
            content = f.read().strip()
            if content:
                parts = content.split(",")
                if len(parts) == 2:
                    last_date, last_count = parts
                    if last_date != today:
                        return 0
                    return int(last_count)
    return 0

def set_last_count(count):
    """Bugünün tarihiyle birlikte son kayıt sayısını dosyaya yaz"""
    with open("last_count.txt", "w") as f:
        f.write(f"{today},{count}")

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
        # publishDate'e göre sırala tüm veri (eski -> yeni)
        for item in data:
            item["publishDateParsed"] = datetime.strptime(item["publishDate"], "%d.%m.%Y %H:%M:%S")
        data_sorted = sorted(data, key=lambda x: x["publishDateParsed"])

        # Sadece en güncel yeni gelenleri al
        diff = new_count - last_count
        new_items_sorted = data_sorted[-diff:]  # en güncel diff kadar

        # sırayla gönder
        for item in new_items_sorted:
            stock = item.get("stockCodes") or item.get("relatedStocks") or ""
            stockCode = stock[:5]
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
            send_telegram(message)

        # sayıyı güncelle
        set_last_count(new_count)
    else:
        print("Yeni bildirim yok, telegrama mesaj gönderilmedi.")

else:
    send_telegram(f"KAP verisi alınamadı! Status Code: {response.status_code}")
