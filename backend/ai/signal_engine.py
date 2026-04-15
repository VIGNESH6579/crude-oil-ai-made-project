import pandas as pd
import numpy as np

class TickBuffer:
    def __init__(self, max_len=1000):
        self.ticks = []
        self.max_len = max_len
        
    def add(self, tick):
        self.ticks.append(tick)
        if len(self.ticks) > self.max_len:
            self.ticks.pop(0)
            
    def get_df(self):
        return pd.DataFrame(self.ticks)

buffer = TickBuffer()

from datetime import datetime, time, timedelta

def analyze_tick(current_tick: dict) -> dict:
    # 0. SESSION TIME GATE (MCX Crude Oil IST)
    # Render servers run in UTC, converting to IST:
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_time = ist_now.time()
    
    VALID_SESSIONS = [
        (time(9, 0), time(10, 0)),    # MCX morning session open
        (time(14, 30), time(15, 30)), # EIA inventory data window
        (time(19, 30), time(20, 30)), # US market open & high volume
    ]
    
    # Allow simulated ticks to bypass time gate for backtesting
    is_valid_session = current_tick.get('timestamp') == 'SIMULATED' or current_tick.get('timestamp') == 'FALLBACK' or any(start <= current_time <= end for start, end in VALID_SESSIONS)
    
    if not is_valid_session:
        return {"status": "OUT_OF_SESSION", "message": "Market is outside of core high-volume sessions."}

    buffer.add(current_tick)
    df = buffer.get_df()
    
    if len(df) < 20: 
        return {"status": "WARMUP", "message": "Collecting market tick liquidity..."}
        
    current_price = current_tick['price']
    
    # 1. SPREAD FILTER
    best_bid = current_tick.get('best_bid', current_price)
    best_ask = current_tick.get('best_ask', current_price)
    spread = best_ask - best_bid
    if spread > 10.0:  # Threshold for Crude Oil
        return {"status": "SKIP", "message": f"Spread too wide: {round(spread, 2)} pts"}

    # 2. ADAPTIVE THRESHOLD (Linear Scaling via Volatility)
    recent_prices = df['price'].tail(20)
    recent_range = recent_prices.max() - recent_prices.min()
    max_volatility = 30.0 
    volatility_factor = min(recent_range / max_volatility, 1.0)
    adaptive_threshold = 0.2 + (volatility_factor * 0.4) # Scales 0.2 to 0.6

    # 3. PERSISTENCE FILTER (Weighted Score)
    imbalances = (df['bid_qty'] - df['ask_qty']) / (df['bid_qty'] + df['ask_qty'] + 1e-9)
    imbalance_score = imbalances.tail(3).mean()

    # 4. VOLUME CONFIRMATION (Directional Bias)
    last_10 = df.tail(10).copy()
    last_10['price_change'] = last_10['price'].diff()
    last_10['vol_change'] = last_10['volume'].diff().abs()
    
    buy_volume = last_10[last_10['price_change'] > 0]['vol_change'].sum() + 1e-9
    sell_volume = last_10[last_10['price_change'] < 0]['vol_change'].sum() + 1e-9

    # 5. DYNAMIC TARGET & SL (Clamping Layer)
    raw_sl = 0.5 * max(recent_range, 8.0) 
    sl_pts = min(max(raw_sl, 6.0), 20.0) 
    target_pts = sl_pts * 1.8
    
    returns = df['price'].pct_change().dropna()
    momentum = returns.tail(10).sum()
    
    signal = "NEUTRAL"
    confidence = 0.0
    strike = None
    target = None
    sl = None
    
    # --- AI VALIDATION STUB (Future-proof) ---
    def validate_with_ai_filter(proposed_action, context):
        # In the future, this checks an LLM endpoint: "Does this market context justify a {proposed_action}?"
        # For now, it passes (veto = False). Saves 90% latency compared to LLM-GENERATED signals.
        return True
    
    if imbalance_score > adaptive_threshold and momentum > 0:
        if buy_volume > (sell_volume * 1.3): # Volume Spikes
            if validate_with_ai_filter("BUY", {"imbalance": imbalance_score, "vol_diff": buy_volume - sell_volume}):
                signal = "BUY"
                confidence = min(0.98, 0.5 + abs(imbalance_score) * 0.5)
                rounded_strike = round(current_price / 100) * 100
                strike_price = rounded_strike if rounded_strike >= current_price else rounded_strike + 100
                strike = f"{int(strike_price)} CE" 
                target = f"{round(current_price + target_pts, 2)}"
                sl = f"{round(current_price - sl_pts, 2)}"
            
    elif imbalance_score < -adaptive_threshold and momentum < 0:
        if sell_volume > (buy_volume * 1.3): # Volume Spikes
            if validate_with_ai_filter("SELL", {"imbalance": imbalance_score, "vol_diff": sell_volume - buy_volume}):
                signal = "SELL"
                confidence = min(0.98, 0.5 + abs(imbalance_score) * 0.5)
                rounded_strike = round(current_price / 100) * 100
                strike_price = rounded_strike if rounded_strike <= current_price else rounded_strike - 100
                strike = f"{int(strike_price)} PE" 
                target = f"{round(current_price - target_pts, 2)}"
                sl = f"{round(current_price + sl_pts, 2)}"
            
    return {
        "status": "ACTIVE",
        "action": signal,
        "confidence": confidence,
        "current_ltp": current_price,
        "imbalance": round(imbalance_score, 2),
        "suggested_strike": strike,
        "target": target,
        "stop_loss": sl
    }
