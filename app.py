import hmac
import logging
import os

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

ALLOWED_FIELDS = (
    "signal", "symbol", "tf", "state", "bias_h1", "bias_m15",
    "entry", "sl", "tp1", "tp2", "tp3", "rr", "session", "time",
)


@app.get("/")
def home():
    return jsonify(status="online")


@app.get("/health")
def health():
    return jsonify(status="ok", configured=bool(BOT_TOKEN and CHAT_ID and WEBHOOK_SECRET))


@app.post("/webhook")
def webhook():
    if not WEBHOOK_SECRET:
        return jsonify(error="Webhook not configured"), 503
    provided = request.headers.get("X-Webhook-Secret", "")
    if not hmac.compare_digest(provided, WEBHOOK_SECRET):
        return jsonify(error="Unauthorized"), 401
    if not request.is_json:
        return jsonify(error="JSON required"), 415
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON object required"), 400
    if not BOT_TOKEN or not CHAT_ID:
        return jsonify(error="Telegram not configured"), 503
    message = "\n".join(f"{key.upper()}: {str(data.get(key, ''))[:160]}" for key in ALLOWED_FIELDS)
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            app.logger.error("Telegram API rejected message")
            return jsonify(error="Telegram delivery failed"), 502
    except (requests.RequestException, ValueError):
        app.logger.exception("Telegram delivery failed")
        return jsonify(error="Telegram delivery failed"), 502
    return jsonify(status="sent")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050)
