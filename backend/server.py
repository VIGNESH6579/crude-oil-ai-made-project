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
        message = f"🚨 {action} Signal Alert!\nOption: {strike}\nTarget: {target}\nStop Loss: {sl}"
        
        headers = {
            "Title": f"Crude Oil Scalp: {action}",
            "Tags": "warning" if action == "SELL" else "chart_with_upwards_trend"
        }
        
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=message.encode('utf-8'), headers=headers)
        print(f"Notification sent to {NTFY_TOPIC}")
    except Exception as e:
        print(f"Failed to send NTFY notification: {e}")

def process_signal_and_notify(signal):
    global last_notified_signal
    current_action = signal.get("action", "NEUTRAL")
    
    # Only notify on new Buy/Sell triggers, not repeated ticks
    if current_action in ["BUY", "SELL"] and current_action != last_notified_signal:
        send_ntfy_alert(signal)
        
    # Reset when neutral or changed
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
            try:
                url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
                data = requests.get(url).json()
                crude_tokens = []
                for item in data:
                    if item.get("exch_seg") == "MCX" and item.get("name") == "CRUDEOIL" and item.get("instrumenttype", "").upper() == "FUTCOM":
                        crude_tokens.append(item)
                if crude_tokens:
                    crude_tokens.sort(key=lambda x: x.get("expiry", ""))
                    print(f"Auto-fetched Crude Token: {crude_tokens[0]['token']} Expiry: {crude_tokens[0]['expiry']}")
                    return crude_tokens[0]["token"]
            except Exception as e:
                print("Failed to auto-fetch token:", e)
            return "225431"

        TARGET_TOKEN = os.getenv("CRUDE_TOKEN") or get_active_crude_token()
        main_loop = asyncio.get_running_loop()
        
        def on_tick_received(tick_data):
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
            try:
                # Returns false immediately if login fails
                broker.connect_websocket(TARGET_TOKEN, on_tick_received)
            except Exception as e:
                print(f"Broker thread died with error: {e}")
            
            # If we reach here, Angel Broking failed to login or disconnected unexpectedly
            print("CRITICAL: Angel Broking stream inactive. Falling back to dynamic simulation...")
            
            # Fallback to simulated loop locally so frontend doesn't flatline
            base_price = 6500.0
            import random
            while True:
                import time
                tick_price = base_price + random.uniform(-1.5, 1.5)
                base_price = tick_price
                
                tick_data = {
                    "symbol": "CRUDEOIL (Sim)",
                    "price": round(tick_price, 2),
                    "volume": random.randint(100, 5000),
                    "bid_qty": random.randint(50, 400),
                    "ask_qty": random.randint(50, 400),
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
                time.sleep(0.5)

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
                    "timestamp": "SIMULATED"
                }
                
                signal = analyze_tick(tick_data)
                process_signal_and_notify(signal)
                
                payload = {"tick": tick_data, "signal": signal}
                await manager.broadcast(json.dumps(payload))
                await asyncio.sleep(0.3) # Fast data simulation
        else:
            # Just keep connection open, background thread pushes data
            while True:
                await asyncio.sleep(1)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

@app.get("/")
def read_root():
    return {"status": "Crude Oil Trading Backend Active."}
