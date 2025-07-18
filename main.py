import os
import time
import hashlib
import smtplib
import requests
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv()

# Load credentials from .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Target website URL
URL = "https://example.com"

# Optional: Path to EdgeDriver executable
EDGE_DRIVER_PATH = "msedgedriver.exe"

# Initialize previous hash
previous_hash = None

def get_website_content(url):
    options = EdgeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    service = EdgeService(executable_path=EDGE_DRIVER_PATH)
    driver = webdriver.Edge(service=service, options=options)
    driver.get(url)
    content = driver.page_source
    driver.quit()
    return content

def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

def send_email(subject, message):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)

def main():
    global previous_hash
    print("🔄 Monitoring started...")

    while True:
        try:
            content = get_website_content(URL)
            current_hash = hash_content(content)

            if previous_hash is None:
                previous_hash = current_hash
                print("✅ First content loaded. Hash stored.")
            elif current_hash != previous_hash:
                print("⚠️ Change detected!")
                previous_hash = current_hash
                send_telegram_message("⚠️ Change detected on the website!")
                send_email("Website Change Detected", "⚠️ A change was detected on the monitored website.")
            else:
                print("✅ No change detected.")

        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(300)  # Wait 5 minutes

if __name__ == "__main__":
    main()
