from flask import Flask, request, render_template_string
import requests
import hashlib
import os
import smtplib
import threading
import time
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)

monitoring_threads = {}

HTML_TEMPLATE = '''
<!doctype html>
<title>Website Change Detector</title>
<h2>🌐 Website Change Detector</h2>
<form method=post>
  <label>Enter URL to monitor:</label><br>
  <input type=text name=url size=50 required placeholder="https://example.com"><br><br>
  <label>Check every (seconds):</label><br>
  <input type=number name=interval min=10 max=3600 value=60><br><br>
  <input type=submit value='Start Monitoring'>
</form>
<p>{{ message }}</p>
'''

def send_email_notification(url):
    subject = "🔔 Website Change Detected"
    body = f"The content at {url} has changed."
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("📧 Email notification sent!")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def send_telegram_notification(url):
    message = f"🔔 Change detected at {url}"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )
        if response.status_code == 200:
            print("📩 Telegram notification sent!")
        else:
            print("⚠️ Telegram message failed.")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def monitor_website(url, interval):
    print(f"👀 Starting monitoring: {url} every {interval} seconds.")
    prev_hash = None

    while True:
        try:
            response = requests.get(url, timeout=10)
            content = response.text
            current_hash = hashlib.md5(content.encode()).hexdigest()

            if prev_hash is None:
                prev_hash = current_hash
            elif current_hash != prev_hash:
                print("🚨 Change detected!")
                send_email_notification(url)
                send_telegram_notification(url)
                prev_hash = current_hash
            time.sleep(interval)
        except Exception as e:
            print(f"❌ Error checking website {url}: {e}")
            break

@app.route('/', methods=['GET', 'POST'])
def home():
    message = ""
    if request.method == 'POST':
        url = request.form['url']
        interval = int(request.form['interval'])

        if url not in monitoring_threads:
            thread = threading.Thread(target=monitor_website, args=(url, interval), daemon=True)
            thread.start()
            monitoring_threads[url] = thread
            message = f"✅ Monitoring started for {url} every {interval} seconds."
        else:
            message = "⚠️ This URL is already being monitored."

    return render_template_string(HTML_TEMPLATE, message=message)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Change port here if needed
    app.run(host='0.0.0.0', port=port, debug=True)
