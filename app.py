from flask import Flask, request
import requests

app = Flask(__name__)

@app.route("/")
def home():
    return "TVBOT ONLINE"

@app.route("/test")
def test():
    return "WEBHOOK TEST OK"

BOT_TOKEN = "8394186084:AAHeWDeMdEVwLuwdgNtm8YUuagxzV0QD0j0"
CHAT_ID = "-100373230227"

@app.route('/webhook', methods=['POST'])
def webhook():

    data = request.json

    signal = data.get("signal", "")
    symbol = data.get("symbol", "")
    entry = data.get("entry", "")
    sl = data.get("sl", "")
    tp1 = data.get("tp1", "")
    tp2 = data.get("tp2", "")
    tp3 = data.get("tp3", "")
    rr = data.get("rr", "")
    session = data.get("session", "")
    tf = data.get("tf", "")

    message = f"""
SIGNAL: {signal}
SYMBOL: {symbol}
TF: {tf}

ENTRY: {entry}
SL: {sl}

TP1: {tp1}
TP2: {tp2}
TP3: {tp3}

RR: {rr}
SESSION: {session}
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message
    })

    return {"status": "ok"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)



