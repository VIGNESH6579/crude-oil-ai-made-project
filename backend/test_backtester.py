import time
import os
from datetime import datetime
from dotenv import load_dotenv
from SmartApi.smartConnect import SmartConnect
from ai.signal_engine import analyze_tick, TickBuffer

load_dotenv()

def fetch_real_historical_data(api_key, symbol_token):
    print(f"Connecting to Angel One with token {symbol_token}...")
    obj = SmartConnect(api_key=api_key)
    
    client_id = os.getenv("CLIENT_ID")
    password = os.getenv("PASSWORD")
    totp_secret = os.getenv("TOTP_SECRET")
    
    if not all([api_key, client_id, password, totp_secret]):
         print("Missing Angel One Credentials in .env! Cannot fetch historical data.")
         return []
         
    import pyotp
    totp = pyotp.TOTP(totp_secret).now()
    data = obj.generateSession(client_id, password, totp)
    if not data['status']:
         print("Angel One Login Failed:", data['message'])
         return []
         
    print("Fetching real historical OHLCV data from Angel One...")
    params = {
        "exchange": "MCX",
        "symboltoken": symbol_token,
        "interval": "ONE_MINUTE",
        "fromdate": "2024-11-01 09:00",
        "todate":   "2024-11-05 23:30" 
    }
    
    hist_data = obj.getCandleData(params)
    if hist_data.get("status") and hist_data.get("data"):
         return hist_data["data"]
    print("Error fetching data:", hist_data)
    return []

def synthesize_ticks_from_ohlcv(candle_data):
    # candle output: [timestamp, open, high, low, close, volume]
    ticks = []
    print(f"Synthesizing {len(candle_data)} 1-minute candles into Level-2 Ticks...")
    
    for c in candle_data:
        ts = c[0]
        o, h, l, c_price, v = c[1], c[2], c[3], c[4], c[5]
        
        # Determine Imbalance Synthesis (If candle is green, bids outpaced asks)
        is_bullish = c_price >= o
        base_qty = max(v / 2, 50) 
        
        if is_bullish:
            bid_qty = base_qty * 1.5
            ask_qty = base_qty * 0.5
        else:
            bid_qty = base_qty * 0.5
            ask_qty = base_qty * 1.5
            
        # Spread Synthesis (Widens proportionally to volatility/range)
        candle_range = h - l
        spread = 1.0 + min((candle_range * 0.1), 5.0)
        
        tick = {
            "symbol": "CRUDEOIL_HIST",
            "price": c_price,
            "volume": v,
            "bid_qty": bid_qty,
            "ask_qty": ask_qty,
            "best_bid": c_price - (spread / 2.0),
            "best_ask": c_price + (spread / 2.0),
            "timestamp": "SIMULATED" # Bypass Time Gate for pure mechanical testing 
        }
        ticks.append(tick)
        
    return ticks

def run_backtest():
    api_key = os.getenv("API_KEY")
    symbol_token = os.getenv("CRUDE_TOKEN", "225431") # fallback default MCX CRUDEOIL
    
    raw_candles = fetch_real_historical_data(api_key, symbol_token)
    if not raw_candles:
        return
        
    dataset = synthesize_ticks_from_ohlcv(raw_candles)
    
    trades = []
    active_trade = None
    
    print("Running Historical Backtest Sequence...")
    for tick in dataset:
        signal_output = analyze_tick(tick)
        
        if active_trade:
            if active_trade['action'] == 'BUY':
                if tick['price'] >= active_trade['target']:
                    trades.append({"result": "WIN", "profit": active_trade['target'] - active_trade['entry']})
                    active_trade = None
                elif tick['price'] <= active_trade['sl']:
                    trades.append({"result": "LOSS", "profit": active_trade['sl'] - active_trade['entry']})
                    active_trade = None
            elif active_trade['action'] == 'SELL':
                if tick['price'] <= active_trade['target']:
                    trades.append({"result": "WIN", "profit": active_trade['entry'] - active_trade['target']})
                    active_trade = None
                elif tick['price'] >= active_trade['sl']:
                    trades.append({"result": "LOSS", "profit": active_trade['entry'] - active_trade['sl']})
                    active_trade = None
            continue
            
        if signal_output.get("action") in ["BUY", "SELL"]:
            try:
                target_f = float(signal_output['target'])
                sl_f = float(signal_output['stop_loss'])
                entry = tick['price']
                
                active_trade = {
                    "action": signal_output["action"],
                    "entry": entry,
                    "target": target_f,
                    "sl": sl_f
                }
            except Exception:
                pass

    print("\n" + "="*30)
    print("HISTORICAL BACKTEST RESULTS")
    print("="*30)
    
    total_trades = len(trades)
    if total_trades == 0:
        print("No trades taken.")
        return
        
    wins = [t for t in trades if t['result'] == 'WIN']
    losses = [t for t in trades if t['result'] == 'LOSS']
    
    win_rate = len(wins) / total_trades
    avg_profit = sum(t['profit'] for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t['profit'] for t in losses) / len(losses)) if losses else 0
    
    expectancy = (win_rate * avg_profit) - ((1 - win_rate) * avg_loss)
    
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate:     {win_rate * 100:.2f}%")
    print(f"Avg Profit:   {avg_profit:.2f} pts")
    print(f"Avg Loss:     {avg_loss:.2f} pts")
    print(f"Expectancy:   {expectancy:.2f} pts / trade")
    print("="*30)

if __name__ == "__main__":
    run_backtest()
