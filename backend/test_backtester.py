import random
import time
from ai.signal_engine import analyze_tick, TickBuffer

def generate_synthetic_ticks(num_ticks=2000):
    ticks = []
    current_price = 6500.0
    
    for i in range(num_ticks):
        # Create trends and noise
        step = random.uniform(-2.0, 2.0)
        # Add a spoofed volume scenario occasionally
        is_spoof = random.random() < 0.05
        
        current_price += step
        bid_qty = random.randint(50, 400)
        ask_qty = random.randint(50, 400)
        
        if is_spoof:
            if step > 0: bid_qty += 5000
            else: ask_qty += 5000
            
        tick = {
            "symbol": "CRUDEOIL_SIM",
            "price": round(current_price, 2),
            "volume": random.randint(10, 500),
            "bid_qty": bid_qty,
            "ask_qty": ask_qty,
            "best_bid": round(current_price - random.uniform(0, 0.5), 2),
            "best_ask": round(current_price + random.uniform(0, 0.5), 2),
            "timestamp": "SIMULATED"
        }
        ticks.append(tick)
    return ticks

def run_backtest():
    print("Generating synthetic market data...")
    dataset = generate_synthetic_ticks(5000)
    
    trades = []
    active_trade = None
    
    print("Running Backtest Simulation...")
    for i, tick in enumerate(dataset):
        # Feed tick to engine
        signal_output = analyze_tick(tick)
        
        # If in a trade, check SL or Target hit
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
            continue # Don't take a new trade until current is closed
            
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
            except Exception as e:
                pass

    print("\n" + "="*30)
    print("BACKTEST RESULTS")
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
