import os
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import time

# --- إعداد نظام تسجيل الأخطاء ---
logging.basicConfig(
    filename='bot_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

TELEGRAM_BOT_TOKEN = "8733239782:AAFgTANZqzFSa1LF5E57_mPJIBOJIlHnou0"
TELEGRAM_CHAT_ID = "5620413191"

INITIAL_BALANCE = 200.0     
BASE_RISK_PERCENTAGE = 0.02   
LEVERAGE = 10                  
MAX_TOTAL_MARGIN_RATIO = 0.6  

TRADE_FILE = "active_scalper_trades.csv"
CLOSED_FILE = "closed_scalper_trades_history.csv"
HEARTBEAT_FILE = "last_scalper_heartbeat.txt"

PIONEX_SYMBOLS = {
    "BTCUSDT": "BTC_USDT",
    "ETHUSDT": "ETH_USDT",
    "SOLUSDT": "SOL_USDT",
    "XRPUSDT": "XRP_USDT",
    "ADAUSDT": "ADA_USDT",
    "AVAXUSDT": "AVAX_USDT",
    "LINKUSDT": "LINK_USDT",
    "DOGEUSDT": "DOGE_USDT",
    "SUIUSDT": "SUI_USDT",
    "NEARUSDT": "NEAR_USDT",
    "PEPEUSDT": "PEPE_USDT",
    "RENDERUSDT": "RENDER_USDT",
    "FETUSDT": "FET_USDT",
    "INJUSDT": "INJ_USDT"
}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[-] Telegram Error: {e}")
        logging.error(f"Telegram Error: {e}")

def check_daily_report(active_trades_count, current_balance):
    now = datetime.now(timezone.utc)
    send_report = False
    if os.path.exists(HEARTBEAT_FILE):
        try:
            with open(HEARTBEAT_FILE, "r") as f:
                last_time = datetime.fromisoformat(f.read().strip())
                if (now - last_time) >= timedelta(hours=12):
                    send_report = True
        except Exception:
            send_report = True
    else:
        send_report = True

    if send_report:
        wins, losses, total_pnl = 0, 0, 0.0
        if os.path.exists(CLOSED_FILE):
            try:
                df_closed = pd.read_csv(CLOSED_FILE)
                if not df_closed.empty:
                    wins = len(df_closed[df_closed['Result'] == 'WIN'])
                    losses = len(df_closed[df_closed['Result'] == 'LOSS'])
                    total_pnl = df_closed['PnL'].sum()
            except Exception:
                pass

        roi_percent = ((current_balance - INITIAL_BALANCE) / INITIAL_BALANCE) * 100
        report_msg = (
            f"⚡ *Sniper Scalper (10x Pro Report)*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ الوقت: `{now.strftime('%Y-%m-%d %H:%M:%S')} UTC`\n"
            f"💰 الرصيد الحالي: `${current_balance:.2f}` (ROI: `{roi_percent:+.2f}%`)\n"
            f"📈 إجمالي الأرباح/الخسائر: `${total_pnl:+.2f}`\n"
            f"🎯 صفقات رابحة: `{wins}` | 🛑 صفقات خاسرة: `{losses}`\n"
            f"📂 الصفقات النشطة حالياً: `{active_trades_count}`\n"
            f"🚀 *الحالة:* البوت يعمل بكفاءة عالية على اللابتوب 24/7."
        )
        send_telegram_message(report_msg)
        try:
            with open(HEARTBEAT_FILE, "w") as f:
                f.write(now.isoformat())
        except Exception as e:
            logging.error(f"Error writing heartbeat: {e}")

def save_closed_trade(trade_data):
    file_exists = os.path.exists(CLOSED_FILE)
    df = pd.DataFrame([trade_data])
    try:
        df.to_csv(CLOSED_FILE, mode='a', header=not file_exists, index=False)
    except Exception as e:
        logging.error(f"Error saving closed trade: {e}")

def get_pionex_candles(symbol, interval="1m", limit=30):
    binance_symbol = symbol.replace("_", "")
    url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={interval}&limit={limit}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            raw_klines = response.json()
            if isinstance(raw_klines, list) and len(raw_klines) > 0:
                df_list = []
                for item in raw_klines:
                    df_list.append({
                        'timestamp': int(item[0]),
                        'open': float(item[1]),
                        'high': float(item[2]),
                        'low': float(item[3]),
                        'close': float(item[4]),
                        'volume': float(item[5])
                    })
                return pd.DataFrame(df_list)
        return None
    except Exception as e:
        logging.error(f"Error fetching {symbol}: {e}")
        return None

def calculate_rsi(series, period=5):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def manage_and_scan_scalper_market():
    print(f"\n[+] Scanning market at {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC...")
    current_balance = INITIAL_BALANCE
    if os.path.exists(CLOSED_FILE):
        try:
            df_closed = pd.read_csv(CLOSED_FILE)
            if not df_closed.empty and 'PnL' in df_closed.columns:
                current_balance = INITIAL_BALANCE + df_closed['PnL'].sum()
        except Exception as e:
            logging.error(f"Error reading history: {e}")

    active_trades = []
    if os.path.exists(TRADE_FILE):
        try:
            active_trades = pd.read_csv(TRADE_FILE).to_dict('records')
        except Exception:
            pass

    updated_trades = []
    open_symbols = [t['Symbol'] for t in active_trades]

    for trade in active_trades:
        symbol = trade['Symbol']
        pionex_symbol = PIONEX_SYMBOLS.get(symbol, f"{symbol.replace('USDT', '_USDT')}")
        df = get_pionex_candles(pionex_symbol, interval="1m", limit=5)
        if df is None or df.empty:
            updated_trades.append(trade)
            continue
            
        curr_price = df.iloc[-1]['close']
        entry = trade['Entry']
        tp1 = trade['TP1']
        tp2 = trade['TP2']
        tp3 = trade['TP3']
        sl = trade['SL']
        qty = trade['Qty']
        side = trade['Side']
        hit_stage = int(trade.get('HitStage', 0))

        closed = False
        utc_now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        if side == "LONG":
            if curr_price <= sl:
                loss = (entry - sl) * qty * LEVERAGE if sl != entry else 0.0
                result_status = 'NEUTRAL' if sl == entry else 'LOSS'
                send_telegram_message(f"🛑 *Sniper: SL Hit (LONG {symbol}) 10x*\n📉 الخسارة: `-${loss:.2f}`")
                save_closed_trade({'Timestamp': utc_now_str, 'Symbol': symbol, 'Side': side, 'Entry': entry, 'Exit': sl, 'Result': result_status, 'Reason': 'SL Hit', 'PnL': round(-loss, 2)})
                closed = True
            else:
                if hit_stage < 3 and curr_price >= tp3:
                    profit = (tp3 - entry) * qty * LEVERAGE
                    send_telegram_message(f"🎯 *Sniper: TP3 Final Hit! (LONG {symbol}) 10x*\n💰 الربح المحقق: `+${profit:.2f}`")
                    save_closed_trade({'Timestamp': utc_now_str, 'Symbol': symbol, 'Side': side, 'Entry': entry, 'Exit': tp3, 'Result': 'WIN', 'Reason': 'TP3', 'PnL': round(profit, 2)})
                    closed = True
                elif hit_stage < 2 and curr_price >= tp2:
                    trade['HitStage'] = 2
                    trade['SL'] = tp1
                    send_telegram_message(f"🚀 *Sniper: TP2 Hit (LONG {symbol})*\n🔒 تم نقل الوقف إلى TP1 لحماية الأرباح")
                    updated_trades.append(trade)
                elif hit_stage < 1 and curr_price >= tp1:
                    trade['HitStage'] = 1
                    trade['SL'] = entry
                    send_telegram_message(f"📈 *Sniper: TP1 Hit (LONG {symbol})*\n🛡️ تأمين الصفقة عند نقطة الدخول (Break-Even)")
                    updated_trades.append(trade)
                else:
                    if not closed and trade not in updated_trades:
                        updated_trades.append(trade)

        elif side == "SHORT":
            if curr_price >= sl:
                loss = (sl - entry) * qty * LEVERAGE if sl != entry else 0.0
                result_status = 'NEUTRAL' if sl == entry else 'LOSS'
                send_telegram_message(f"🛑 *Sniper: SL Hit (SHORT {symbol}) 10x*\n📉 الخسارة: `-${loss:.2f}`")
                save_closed_trade({'Timestamp': utc_now_str, 'Symbol': symbol, 'Side': side, 'Entry': entry, 'Exit': sl, 'Result': result_status, 'Reason': 'SL Hit', 'PnL': round(-loss, 2)})
                closed = True
            else:
                if hit_stage < 3 and curr_price <= tp3:
                    profit = (entry - tp3) * qty * LEVERAGE
                    send_telegram_message(f"🎯 *Sniper: TP3 Final Hit! (SHORT {symbol}) 10x*\n💰 الربح المحقق: `+${profit:.2f}`")
                    save_closed_trade({'Timestamp': utc_now_str, 'Symbol': symbol, 'Side': side, 'Entry': entry, 'Exit': tp3, 'Result': 'WIN', 'Reason': 'TP3', 'PnL': round(profit, 2)})
                    closed = True
                elif hit_stage < 2 and curr_price <= tp2:
                    trade['HitStage'] = 2
                    trade['SL'] = tp1
                    send_telegram_message(f"🚀 *Sniper: TP2 Hit (SHORT {symbol})*\n🔒 تم نقل الوقف إلى TP1 لحماية الأرباح")
                    updated_trades.append(trade)
                elif hit_stage < 1 and curr_price <= tp1:
                    trade['HitStage'] = 1
                    trade['SL'] = entry
                    send_telegram_message(f"📉 *Sniper: TP1 Hit (SHORT {symbol})*\n🛡️ تأمين الصفقة عند نقطة الدخول (Break-Even)")
                    updated_trades.append(trade)
                else:
                    if not closed and trade not in updated_trades:
                        updated_trades.append(trade)

    for symbol, pionex_symbol in PIONEX_SYMBOLS.items():
        if len(updated_trades) >= 5:
            break  
        if symbol in open_symbols:
            continue
            
        df = get_pionex_candles(pionex_symbol, interval="1m", limit=15)
        if df is None or len(df) < 10:
            continue
            
        df['ema2'] = df['close'].ewm(span=2, adjust=False).mean()
        df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
        df['rsi'] = calculate_rsi(df['close'], period=5)
        df['vol_avg'] = df['volume'].rolling(window=5).mean()
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        curr_price = curr['close']
        
        has_volume = curr['volume'] >= (curr['vol_avg'] * 0.8)

        is_long = (prev['ema2'] <= prev['ema5']) and (curr['ema2'] > curr['ema5']) and (curr['rsi'] > 38) and has_volume
        is_short = (prev['ema2'] >= prev['ema5']) and (curr['ema2'] < curr['ema5']) and (curr['rsi'] < 62) and has_volume

        if is_long:
            entry = curr_price
            sl = entry * 0.996
            risk_dist = entry - sl
            tp1 = entry * 1.003
            tp2 = entry * 1.006 
            tp3 = entry * 1.010 

            risk_amount = current_balance * BASE_RISK_PERCENTAGE
            qty = risk_amount / risk_dist if risk_dist > 0 else 1.0
            
            if qty > 0:
                new_trade = {
                    'Symbol': symbol, 'Side': 'LONG', 'Entry': entry,
                    'TP1': tp1, 'TP2': tp2, 'TP3': tp3, 'SL': sl, 'Qty': qty, 'HitStage': 0
                }
                updated_trades.append(new_trade)
                open_symbols.append(symbol)
                
                send_telegram_message(
                    f"⚡ *Sniper LONG Signal (10x)*\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🔹 الرمز: `{symbol}` | الدخول: `{entry:.4f}`\n"
                    f"🎯 TP1: `{tp1:.4f}` | TP2: `{tp2:.4f}` | TP3: `{tp3:.4f}`\n"
                    f"🛑 Stop Loss: `{sl:.4f}` (0.4%)\n"
                    f"💵 الرصيد المتاح: `${current_balance:.2f}`"
                )

        elif is_short:
            entry = curr_price
            sl = entry * 1.004
            risk_dist = sl - entry
            tp1 = entry * 0.997 
            tp2 = entry * 0.994 
            tp3 = entry * 0.990 

            risk_amount = current_balance * BASE_RISK_PERCENTAGE
            qty = risk_amount / risk_dist if risk_dist > 0 else 1.0
            
            if qty > 0:
                new_trade = {
                    'Symbol': symbol, 'Side': 'SHORT', 'Entry': entry,
                    'TP1': tp1, 'TP2': tp2, 'TP3': tp3, 'SL': sl, 'Qty': qty, 'HitStage': 0
                }
                updated_trades.append(new_trade)
                open_symbols.append(symbol)
                
                send_telegram_message(
                    f"⚡ *Sniper SHORT Signal (10x)*\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🔹 الرمز: `{symbol}` | الدخول: `{entry:.4f}`\n"
                    f"🎯 TP1: `{tp1:.4f}` | TP2: `{tp2:.4f}` | TP3: `{tp3:.4f}`\n"
                    f"🛑 Stop Loss: `{sl:.4f}` (0.4%)\n"
                    f"💵 الرصيد المتاح: `${current_balance:.2f}`"
                )

    if updated_trades:
        df_out = pd.DataFrame(updated_trades).drop_duplicates(subset=['Symbol'])
        df_out.to_csv(TRADE_FILE, index=False)
    else:
        if os.path.exists(TRADE_FILE):
            os.remove(TRADE_FILE)

    check_daily_report(len(updated_trades), current_balance)
    print("[+] Scan cycle completed successfully. Waiting for next cycle...")

if __name__ == "__main__":
    print("Starting Sniper Scalper Bot 10x...")
    while True:
        try:
            manage_and_scan_scalper_market()
        except Exception as e:
            print(f"[-] Loop Error: {e}")
            logging.error(f"Sniper Loop Error: {e}")
        
        time.sleep(10)