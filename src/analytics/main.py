import time
import os
import sys
sys.path.append(os.getcwd())
from src.common.redis_client import RedisClient
from src.analytics.welford import WelfordState

SYMBOL = os.getenv("SYMBOL", "btcusdt")
GROUP_NAME = "analytics_workers"
CONSUMER_NAME = "worker_1"

def process_stream():
    redis_db = RedisClient()
    redis_db.create_consumer_group(GROUP_NAME)
    
    # Initialize Analytics State
    price_stats = WelfordState()
    
    print(f"🧠 Analytics Worker Started for {SYMBOL}")
    
    while True:
        # Read new messages from the stream
        # '>' means "give me messages never delivered to other consumers"
        events = redis_db.client.xreadgroup(
            GROUP_NAME, CONSUMER_NAME, {redis_db.stream_key: ">"}, count=10, block=1000
        )
        
        if not events:
            continue
            
        for _, messages in events:
            for message_id, data in messages:
                price = float(data['price'])
                
                # 1. Update Math
                price_stats.update(price)
                current_z = price_stats.z_score(price)
                
                # 2. Publish "Hot" State for Dashboard
                system_state = {
                    "symbol": data['symbol'],
                    "price": price,
                    "mean": price_stats.mean,
                    "std": price_stats.std_dev,
                    "z_score": current_z,
                    "timestamp": data['timestamp']
                }
                redis_db.update_state(SYMBOL, system_state)
                
                # 3. Acknowledge message processed
                redis_db.client.xack(redis_db.stream_key, GROUP_NAME, message_id)

if __name__ == "__main__":
    process_stream()