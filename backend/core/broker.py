import os
import pyotp
import logging
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from dotenv import load_dotenv

load_dotenv()

# Logger setup
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class AngelBroker:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.client_id = os.getenv("CLIENT_ID")
        self.password = os.getenv("PASSWORD") # PIN
        self.totp_secret = os.getenv("TOTP_SECRET")
        self.feed_token = None
        self.sws = None
        self.smart_api = None

    def login(self):
        try:
            self.smart_api = SmartConnect(api_key=self.api_key)
            totp = pyotp.TOTP(self.totp_secret).now()
            data = self.smart_api.generateSession(self.client_id, self.password, totp)
            
            if data['status'] == False:
                logger.error(data['message'])
                return False
                
            self.feed_token = self.smart_api.getfeedToken()
            self.auth_token = data['data']['jwtToken']
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def connect_websocket(self, token, on_message_callback):
        if not self.feed_token:
            if not self.login():
                return
                
        # Angel One correlation ID (string)
        correlation_id = "ai_scalper_1"
        
        # Action: 1 (Subscribe), Mode: 3 (SnapQuote)
        mode = 3 
        
        # Token needs to be in format "{exchange}|{token}" e.g., "MCX|223293"
        token_list = [{"exchangeType": 5, "tokens": [token]}] # 5 represents MCX

        self.sws = SmartWebSocketV2(
            auth_token=self.auth_token,
            api_key=self.api_key,
            client_code=self.client_id,
            feed_token=self.feed_token
        )
        
        def on_data(wsapp, message, *args):
            tick_data = self._parse_tick(message)
            if tick_data:
                on_message_callback(tick_data)

        self.sws.on_data = on_data
        
        def on_open(wsapp, *args):
            logger.info("WebSocket connection opened. Subscribing to tokens...")
            try:
                self.sws.subscribe(correlation_id, mode, token_list)
            except Exception as e:
                logger.error(f"Subscribe failed: {e}")

        self.sws.on_open = on_open
        self.sws.connect()

    def _parse_tick(self, message):
        """
        Map Angel broker snap quote (mode 3) to our model's tick object.
        """
        try:
            if 'best_5_buy_data' in message and 'last_traded_price' in message:
                ltp = message['last_traded_price'] / 100.0
                volume = message.get('volume_trade_for_the_day', 0)
                
                bid_qty = sum([b['quantity'] for b in message.get('best_5_buy_data', [])])
                ask_qty = sum([a['quantity'] for a in message.get('best_5_sell_data', [])])
                
                return {
                    "symbol": "CRUDEOIL",
                    "price": ltp,
                    "volume": volume,
                    "bid_qty": bid_qty,
                    "ask_qty": ask_qty,
                    "timestamp": message.get('exchange_timestamp')
                }
            elif 'last_traded_price' in message:
                return {
                    "symbol": "CRUDEOIL",
                    "price": message['last_traded_price'] / 100.0,
                    "volume": 0,
                    "bid_qty": 50,
                    "ask_qty": 50,
                    "timestamp": message.get('exchange_timestamp')
                }
        except Exception as e:
            logger.error(f"Parse error: {e}")
        return None
