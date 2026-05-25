from flask import Flask, request
import requests

app = Flask(__name__)

# =========================
# TELEGRAM CONFIG
# =========================

BOT_TOKEN = "8394186084:AAHeWDeMdEvwLuWdgNtm8YUaagxzV0QD0j0"

# ห้อง VVIP GROUP
CHAT_ID = "-100373230227"

# =========================
# HOME 
# =========================

@app.route("/")
def home():
    return "TVBOT ONLINE"

# =========================
# TEST PAGE
# =========================

@app.route("/test")
def test():
    return "WEBHOOK TEST OK"

# =========================
# WEBHOOK
# =========================

@app.route('/webhook', methods=['POST'])
def webhook():

    data = request.json

    print("RAW DATA:", data)

    signal = data.get("signal", "")
    symbol = data.get("symbol", "")
    tf = data.get("tf", "")

    state = data.get("state", "")
    bias_h1 = data.get("bias_h1", "")
    bias_m15 = data.get("bias_m15", "")

    entry = data.get("entry", "")
    sl = data.get("sl", "")

    tp1 = data.get("tp1", "")
    tp2 = data.get("tp2", "")
    tp3 = data.get("tp3", "")

    rr = data.get("rr", "")
    session = data.get("session", "")
    time_value = data.get("time", "")

    message = f"""
SIGNAL: {signal}

SYMBOL: {symbol}
TF: {tf}

STATE: {state}

BIAS_H1: {bias_h1}
BIAS_M15: {bias_m15}

ENTRY: {entry}
SL: {sl}

TP1: {tp1}
TP2: {tp2}
TP3: {tp3}

RR: {rr}

SESSION: {session}

TIME: {time_value}
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message
        }
    )

    print("TELEGRAM RESPONSE:", response.text)

    return {"status": "ok"}

# =========================
# RUN APP
# =========================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)
