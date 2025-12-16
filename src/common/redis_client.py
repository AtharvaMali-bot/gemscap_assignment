import redis
import os
import json

class RedisClient:
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.client = redis.Redis(host=self.host, port=6379, decode_responses=True)
        self.stream_key = "market_stream"
        self.state_key_prefix = "market_state"

    def publish_tick(self, tick_data):
        """Push a normalized tick to the Redis Stream"""
        # Maxlen ensures we don't run out of RAM if consumer dies
        self.client.xadd(self.stream_key, tick_data, maxlen=10000)

    def get_latest_state(self, symbol):
        """Fetch the calculated analytics for the dashboard"""
        data = self.client.get(f"{self.state_key_prefix}:{symbol}")
        return json.loads(data) if data else None

    def update_state(self, symbol, state_dict):
        """Overwrite the 'Hot' state key with new analytics"""
        self.client.set(f"{self.state_key_prefix}:{symbol}", json.dumps(state_dict))

    def create_consumer_group(self, group_name):
        try:
            self.client.xgroup_create(self.stream_key, group_name, id='0', mkstream=True)
        except redis.exceptions.ResponseError:
            pass  # Group already exists