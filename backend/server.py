import asyncio
import json
import threading
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from core.websocket_manager import ConnectionManager
from core.broker import AngelBroker
from ai.signal_engine import analyze_tick
from dotenv import load_dotenv
import os

from dotenv import load_dotenv
import os
import requests

load_dotenv()

app = FastAPI()

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "vignesh_crude_oil_signals_12345")
last_notified_signal = "NEUTRAL"

def send_ntfy_alert(signal_data):
    try:
        action = signal_data.get("action")
        strike = signal_data.get("suggested_strike")
        target = signal_data.get("target")
        sl = signal_data.get("stop_loss")
        current_ltp = signal_data.get("current_ltp")
        message = f"🚨 {action} Signal Alert!\n📈 Strike: {strike}\n💰 Current Base LTP: {current_ltp}\n🎯 Target LTP: {target}\n🛑 Stop Loss: {sl}\n\n(Base LTP determines direction for Call/Put Options)"
        
        headers = {
            "Title": f"Crude Oil Scalp: {action}",
            "Tags": "warning" if action == "SELL" else "chart_with_upwards_trend"
        }
        
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=message.encode('utf-8'), headers=headers)
        print(f"Notification sent to {NTFY_TOPIC}")
    except Exception as e:
        print(f"Failed to send NTFY notification: {e}")

import time
last_notified_time = 0

def process_signal_and_notify(signal):
    global last_notified_signal, last_notified_time
    current_action = signal.get("action", "NEUTRAL")
    
    # 1. Prevent exact consecutive duplicates
    if current_action in ["BUY", "SELL"] and current_action != last_notified_signal:
        
        # 2. Prevent Flip-Flop Choppy Spam (3-minute minimum cooldown)
        current_time = time.time()
        if (current_time - last_notified_time) > 180:
            send_ntfy_alert(signal)
            last_notified_time = current_time
            
    # Always track the latest sequence so it resets on NEUTRAL
    last_notified_signal = current_action

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
broker = AngelBroker()

# Default to simulation if keys are missing from environment variables
SIMULATION_MODE = not bool(os.getenv("API_KEY", "").strip())

@app.on_event("startup")
async def startup_event():
    # If not simulation, connect to broker in background
    if not SIMULATION_MODE:
        def get_active_crude_token():
            from datetime import datetime
            try:
                url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
                data = requests.get(url).json()
                crude_tokens = []
                for item in data:
                    if item.get("exch_seg") == "MCX" and item.get("name") == "CRUDEOIL" and item.get("instrumenttype", "").upper() == "FUTCOM":
                        crude_tokens.append(item)
                
                def expiry_key(x):
                    exp = x.get("expiry", "")
                    try:
                        return datetime.strptime(exp, "%d%b%Y")
                    except Exception:
                        try:
                            return datetime.strptime(exp, "%d-%b-%Y")
                        except Exception:
                            return datetime.max
                            
                if crude_tokens:
                    crude_tokens.sort(key=expiry_key)
                    # Filter out historically expired contracts (keep only future/today expiries)
                    now = datetime.now()
                    active_tokens = [t for t in crude_tokens if expiry_key(t) >= datetime(now.year, now.month, now.day)]
                    if not active_tokens:
                        active_tokens = crude_tokens
                        
                    print(f"Auto-fetched Crude Token: {active_tokens[0]['token']} Expiry: {active_tokens[0]['expiry']}")
                    return active_tokens[0]["token"], active_tokens[0]["expiry"]
            except Exception as e:
                print("Failed to auto-fetch token:", e)
            return "225431", "UNKNOWN"

        fetch_res = get_active_crude_token()
        if isinstance(fetch_res, tuple):
            TARGET_TOKEN, TARGET_EXPIRY = fetch_res
        else:
            TARGET_TOKEN, TARGET_EXPIRY = fetch_res, "UNKNOWN"
        
        TARGET_TOKEN = os.getenv("CRUDE_TOKEN") or TARGET_TOKEN
        main_loop = asyncio.get_running_loop()
        
        last_tick_time = 0
        global_last_price = 6500.0

        def on_tick_received(tick_data):
            nonlocal last_tick_time, global_last_price
            import time
            last_tick_time = time.time()
            global_last_price = tick_data.get("price", global_last_price)
            tick_data["symbol"] = f"CRUDEOIL ({TARGET_EXPIRY})"
            
            signal = analyze_tick(tick_data)
            process_signal_and_notify(signal)
            
            payload = {"tick": tick_data, "signal": signal}
            # Queue to asyncio loop
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(json.dumps(payload)),
                main_loop
            )
            
        # Run websocket in separate thread since it blocks
        def start_broker():
            import time, random
            
            # Start Angel Broker in daemon thread so it doesn't block watchdog
            def angel_thread():
                try:
                    broker.connect_websocket(TARGET_TOKEN, on_tick_received)
                except Exception as e:
                    print(f"Broker thread died with error: {e}")
                    
            wt = threading.Thread(target=angel_thread)
            wt.daemon = True
            wt.start()
            
            print("Watchdog active. Monitoring Angel Broking stream...")
            
            # Watchdog loop: If no data from Angel One for 30 seconds, pump simulation data!
            nonlocal last_tick_time, global_last_price
            last_tick_time = time.time() - 35 # Force immediate fallback check until first real tick
            
            while True:
                time.sleep(1)
                # Fallback condition: 30 seconds since last tick
                if time.time() - last_tick_time > 30:
                    tick_price = global_last_price + random.uniform(-1.5, 1.5)
                    global_last_price = tick_price
                    
                    tick_data = {
                        "symbol": f"CRUDEOIL ({TARGET_EXPIRY}) - Sim",
                        "price": round(tick_price, 2),
                        "volume": random.randint(100, 5000),
                        "bid_qty": random.randint(50, 400),
                        "ask_qty": random.randint(50, 400),
                        "best_bid": round(tick_price - 1.0, 2),
                        "best_ask": round(tick_price + 1.0, 2),
                        "timestamp": "FALLBACK"
                    }
                    
                    signal = analyze_tick(tick_data)
                    process_signal_and_notify(signal)
                    
                    payload = {"tick": tick_data, "signal": signal}
                    # Queue to asyncio loop
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast(json.dumps(payload)),
                        main_loop
                    )

        t = threading.Thread(target=start_broker)
        t.daemon = True
        t.start()

@app.websocket("/ws/market-data")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        if SIMULATION_MODE:
            # Simulated live data stream specifically for Crude Oil
            base_price = 6500.0
            while True:
                import random
                tick_price = base_price + random.uniform(-1.5, 1.5)
                base_price = tick_price
                
                tick_data = {
                    "symbol": "CRUDEOIL",
                    "price": round(tick_price, 2),
                    "volume": random.randint(100, 5000),
                    "bid_qty": random.randint(50, 400),
                    "ask_qty": random.randint(50, 400),
                    "best_bid": round(tick_price - 1.0, 2),
                    "best_ask": round(tick_price + 1.0, 2),
                    "timestamp": "SIMULATED"
                }
                
                signal = analyze_tick(tick_data)
                process_signal_and_notify(signal)
                
                payload = {"tick": tick_data, "signal": signal}
                await manager.broadcast(json.dumps(payload))
                await asyncio.sleep(0.3) # Fast data simulation
        else:
            # Just keep connection open and periodically read to avoid timeout
            while True:
                try:
                    await websocket.receive_text()
                except Exception:
                    break
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

@app.get("/")
def read_root():
    return {"status": "Crude Oil Trading Backend Active."}

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok", "message": "Backend is healthy"}
