import os
import time
import smtplib
import telegram
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from dotenv import load_dotenv

# Load env variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Path to cache
CACHE_FILE = "cached_content.txt"

def get_website_content(url):
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=options)
    try:
        driver.get(url)
        content = driver.page_source
    finally:
        driver.quit()
    return content

def send_email(subject, body):
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        message = f"Subject: {subject}\n\n{body}"
        smtp.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, message)

def send_telegram(message):
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

def main():
    url = "https://example.com"  # Replace with the target website
    new_content = get_website_content(url)

    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            old_content = f.read()
    else:
        old_content = ""

    if new_content != old_content:
        print("⚠️ Change detected!")
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)

        message = f"Website changed! Check: {url}"
        send_email("📣 Website Change Detected", message)
        send_telegram(message)
    else:
        print("✅ No change detected.")

if __name__ == "__main__":
    while True:
        main()
        print("⏳ Waiting 5 minutes...")
        time.sleep(300)  # 5 minutes
