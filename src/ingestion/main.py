import asyncio
import websockets
import json
import os
import sys
# Add root to path so we can import 'src'
sys.path.append(os.getcwd())
from src.common.redis_client import RedisClient

SYMBOL = os.getenv("SYMBOL", "btcusdt")
WS_URL = f"wss://fstream.binance.com/ws/{SYMBOL}@trade"

async def ingest():
    redis_db = RedisClient()
    print(f"🔌 Connecting to {WS_URL}...")
    
    async for websocket in websockets.connect(WS_URL):
        try:
            print("✅ Connected to Binance.")
            async for message in websocket:
                data = json.loads(message)
                
                # Normalization (The Anti-Corruption Layer)
                normalized_tick = {
                    "timestamp": data['T'],
                    "price": float(data['p']),
                    "volume": float(data['q']),
                    "symbol": data['s']
                }
                
                # Push to Redis Stream
                redis_db.publish_tick(normalized_tick)
                
        except websockets.ConnectionClosed:
            print("⚠️ Connection closed, retrying...")
            continue

if __name__ == "__main__":
    asyncio.run(ingest())