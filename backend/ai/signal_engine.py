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

def analyze_tick(current_tick: dict) -> dict:
    buffer.add(current_tick)
    df = buffer.get_df()
    
    if len(df) < 20: 
        return {"status": "WARMUP", "message": "Collecting market tick liquidity..."}
        
    # Heuristic Signal Generation (Imitation of High-Frequency ML for Options)
    # 1. Order Book Imbalance (Are buyers pushing?)
    recent_bid = df['bid_qty'].tail(5).sum()
    recent_ask = df['ask_qty'].tail(5).sum()
    imbalance = (recent_bid - recent_ask) / (recent_bid + recent_ask + 1e-9)
    
    # 2. Short-term momentum
    returns = df['price'].pct_change().dropna()
    momentum = returns.tail(10).sum()
    
    current_price = current_tick['price']
    
    signal = "NEUTRAL"
    confidence = 0.0
    strike = None
    target = None
    sl = None
    
    # Simple Scalping Logic: If bids heavily outweigh asks AND momentum is positive
    if imbalance > 0.4 and momentum > 0:
        signal = "BUY"
        confidence = min(0.98, 0.5 + abs(imbalance) * 0.5)
        # Options strategy logic
        rounded_strike = round(current_price / 100) * 100
        strike_price = rounded_strike if rounded_strike >= current_price else rounded_strike + 100
        strike = f"{int(strike_price)} CE" # Call Option
        target = "15 pts"
        sl = "8 pts"
    elif imbalance < -0.4 and momentum < 0:
        signal = "SELL"
        confidence = min(0.98, 0.5 + abs(imbalance) * 0.5)
        # Options strategy logic
        rounded_strike = round(current_price / 100) * 100
        strike_price = rounded_strike if rounded_strike <= current_price else rounded_strike - 100
        strike = f"{int(strike_price)} PE" # Put Option
        target = "15 pts"
        sl = "8 pts"
        
    return {
        "status": "ACTIVE",
        "action": signal,
        "confidence": confidence,
        "imbalance": round(imbalance, 2),
        "suggested_strike": strike,
        "target": target,
        "stop_loss": sl
    }
