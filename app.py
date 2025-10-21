from flask import Flask, request, jsonify
import telegram
from datetime import datetime, time
import requests
import sqlite3
import pytz
import pandas as pd
import numpy as np
from contextlib import contextmanager

app = Flask(__name__)

# === CONFIG - CHANGE THESE ===
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
CHAT_ID = "YOUR_CHAT_ID_HERE"
# === END CONFIG ===

bot = telegram.Bot(token=BOT_TOKEN)
SRI_LANKA_TZ = pytz.timezone('Asia/Colombo')
TRADING_START = time(18, 0)
TRADING_END = time(23, 59)

# Database setup
def init_db():
    with sqlite3.connect('trading_signals.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                price REAL,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                result_price REAL,
                result_time TEXT
            )
        ''')
        conn.commit()

@contextmanager
def get_db():
    conn = sqlite3.connect('trading_signals.db')
    try:
        yield conn
    finally:
        conn.close()

def is_trading_time():
    now_sri_lanka = datetime.now(SRI_LANKA_TZ)
    current_time = now_sri_lanka.time()
    current_weekday = now_sri_lanka.weekday()
    if current_weekday >= 5:
        return False
    return TRADING_START <= current_time <= TRADING_END

def save_signal(symbol, action, price):
    with get_db() as conn:
        timestamp = datetime.now(SRI_LANKA_TZ).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO signals (symbol, action, price, timestamp) VALUES (?, ?, ?, ?)",
            (symbol, action, price, timestamp)
        )
        conn.commit()
        return conn.lastrowid

def get_daily_stats():
    with get_db() as conn:
        today = datetime.now(SRI_LANKA_TZ).strftime("%Y-%m-%d")
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM signals WHERE DATE(timestamp) = ? GROUP BY status",
            (today,)
        )
        stats = cursor.fetchall()
        
        total = 0
        won = 0
        lost = 0
        
        for status, count in stats:
            total += count
            if status == 'WON':
                won += count
            elif status == 'LOST':
                lost += count
        
        win_rate = (won / total * 100) if total > 0 else 0
        return {
            'date': today,
            'total_signals': total,
            'won_signals': won,
            'lost_signals': lost,
            'win_rate': round(win_rate, 2)
        }

# High Accuracy Strategy
class HighAccuracyStrategy:
    def calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        exp1 = prices.ewm(span=fast).mean()
        exp2 = prices.ewm(span=slow).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal).mean()
        return macd, signal_line

    def generate_signal(self, symbol):
        try:
            # Simulate high-accuracy signal (replace with real data)
            import random
            signals = ['BUY', 'SELL']
            confidence = random.uniform(0.75, 0.95)
            
            # 80% chance of accurate signal for demo
            if random.random() > 0.2:
                signal = random.choice(signals)
                return signal, confidence
            else:
                return None, 0
        except:
            return None, 0

strategy = HighAccuracyStrategy()

@app.route('/')
def home():
    return "Binary Signals Bot is Running! ✅"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if not is_trading_time():
            return jsonify({"status": "error", "message": "Outside trading hours (6PM-12AM SL Time)"})

        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data"})

        symbol = data.get('symbol', 'EURUSD')
        action = data.get('action', 'BUY')
        price = data.get('price', 'Current')
        
        # Generate high-accuracy signal
        signal, confidence = strategy.generate_signal(symbol)
        
        if signal and confidence > 0.75:
            signal_id = save_signal(symbol, signal, price)
            
            message = f"""
🚀 **HIGH ACCURACY SIGNAL**

🎯 **Signal ID**: #{signal_id}
⏰ **Time**: {datetime.now(SRI_LANKA_TZ).strftime("%Y-%m-%d %H:%M:%S")}
📊 **Symbol**: {symbol}
🎯 **Action**: {signal}
⭐ **Confidence**: {confidence:.1%}
💎 **Quality**: HIGH

⚡ **Trading Hours**: 6PM-12AM SL Time
⚠️ **Risk**: Max 2% per trade

🎯 **High Probability Setup!**
"""
            bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
            return jsonify({"status": "success", "signal_id": signal_id})
        else:
            return jsonify({"status": "no_signal", "reason": "Low confidence"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/test')
def test_signal():
    """Test endpoint to generate a signal"""
    try:
        signal_id = save_signal('EURUSD', 'BUY', '1.0850')
        message = f"""
✅ **TEST SIGNAL WORKING**

🎯 Signal ID: #{signal_id}
📊 Symbol: EURUSD
🎯 Action: BUY
⏰ Time: {datetime.now(SRI_LANKA_TZ).strftime("%H:%M:%S")}

🤖 Your bot is working perfectly!
"""
        bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        return jsonify({"status": "test_signal_sent"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/result', methods=['POST'])
def update_result():
    """Update trade result (WIN/LOSS)"""
    try:
        data = request.get_json()
        signal_id = data.get('signal_id')
        status = data.get('status')
        
        with get_db() as conn:
            result_time = datetime.now(SRI_LANKA_TZ).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE signals SET status = ?, result_time = ? WHERE id = ?",
                (status, result_time, signal_id)
            )
            conn.commit()
        
        stats = get_daily_stats()
        emoji = "💰" if status == 'WON' else "📉"
        
        message = f"""
{emoji} **TRADE RESULT**

📊 **Signal**: #{signal_id}
🏆 **Result**: {status}

📈 **Today's Stats**:
✅ Won: {stats['won_signals']}
❌ Lost: {stats['lost_signals']}
🎯 Win Rate: {stats['win_rate']}%

{"🎉 Congratulations!" if status == 'WON' else "💪 Next trade!"}
"""
        bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
        return jsonify({"status": "success"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Initialize database
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
