import random
import time
import json
from datetime import datetime, timedelta
import os
import sys

# Add the current directory to sys.path to allow importing youtube_api
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from youtube_api import YouTubeConnection
except ImportError:
    YouTubeConnection = None

class StreamPilotDataEngine:
    """
    Implements the 4-Layer Data Strategy for StreamPilot AI.
    Layer 1: Pre-Trained Base Intelligence (Simulated YouTube global data)
    Layer 2: Niche Benchmark Database (Aggregated category data)
    Layer 3: User's Channel Data (Historical performance)
    Layer 4: Real-Time Streaming Data (Live telemetry)
    """

    def __init__(self, user_id="user_123", niche="tech"):
        self.user_id = user_id
        self.niche = niche
        self.knowledge_base = {}
        self._initialize_layer1()
        self._initialize_layer2()

    def _initialize_layer1(self):
        """LAYER 1: Pre-Trained Base Models (Trained on 10M+ videos)"""
        print("[LAYER 1] Loading pre-trained base models (simulated 10M+ videos)...")
        self.knowledge_base['global_patterns'] = {
            "optimal_title_length": 55,
            "high_ctr_words": ["best", "vs", "worth it", "review", "2026", "secret", "mistake"],
            "avg_youtube_ctr": 4.5,
            "seasonal_peaks": {"Q4": 1.4, "Summer": 0.8}
        }
        time.sleep(0.5)

    def _initialize_layer2(self):
        """LAYER 2: Niche Benchmark Database"""
        print(f"[LAYER 2] Loading niche benchmarks for '{self.niche}'...")
        niches = {
            "tech": {
                "avg_ctr": 5.8,
                "avg_view_duration": 525, # seconds
                "top_upload_hours": ["14:00", "15:00", "16:00"],
                "avg_cpm": 14.20,
                "trending_subtopics": ["RTX 5090", "AI laptops", "OLED monitors"]
            },
            "gaming": {
                "avg_ctr": 4.2,
                "avg_view_duration": 480,
                "top_upload_hours": ["18:00", "19:00", "20:00"],
                "avg_cpm": 5.50,
                "trending_subtopics": ["GTA VI leaks", "Elden Ring DLC", "Speedruns"]
            }
        }
        self.knowledge_base['niche'] = niches.get(self.niche, niches["tech"])
        time.sleep(0.3)

    def fetch_layer3_data(self):
        """LAYER 3: User's Channel Data (Real OAuth Sync)"""
        print("[LAYER 3] Syncing historical channel data via YouTube API (OAuth)...")

        self.knowledge_base['user'] = {
            "channel_name": "Unknown",
            "subscribers": 0,
            "total_views": 0,
            "video_count": 0,
            "videos": []
        }

        try:
            if YouTubeConnection:
                yt = YouTubeConnection()
                channel_stats = yt.get_channel_stats()
                if channel_stats:
                    stats = channel_stats['statistics']
                    snippet = channel_stats['snippet']
                    self.knowledge_base['user']['channel_name'] = snippet['title']
                    self.knowledge_base['user']['subscribers'] = int(stats.get('subscriberCount', 0))
                    self.knowledge_base['user']['total_views'] = int(stats.get('viewCount', 0))
                    self.knowledge_base['user']['video_count'] = int(stats.get('videoCount', 0))
                    print(f"   -> Real data loaded for: {snippet['title']}")
            else:
                print("   -> YouTubeConnection module not found. Falling back to mock data.")
        except Exception as e:
            print(f"   -> Error fetching real data: {e}. Falling back to mock data.")

        # If we failed to get real subscriber count or it's 0, use mock data so math models don't break
        if self.knowledge_base['user']['subscribers'] == 0:
            self.knowledge_base['user']['subscribers'] = 45000
            self.knowledge_base['user']['total_views'] = 4200000

        # We'll still mock the individual videos for the Kalman filter until we add the playlistItems API call
        for i in range(30):
            days_ago = 30 - i
            video = {
                "id": f"vid_{i}",
                "title": f"Test Video {i}",
                "views": int(random.gauss(12000, 3000)),
                "ctr": round(random.gauss(5.2, 1.0), 1),
                "avd": int(random.gauss(320, 60)), # seconds
                "date": (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            }
            self.knowledge_base['user']['videos'].append(video)

        print(f"   -> Synced {len(self.knowledge_base['user']['videos'])} historical videos.")
        return self.knowledge_base['user']

    def stream_layer4_telemetry(self):
        """LAYER 4: Real-Time Streaming Data Generator"""
        # Yields a continuous stream of live data (simulated Websocket)
        base_viewers = random.randint(500, 2000)
        while True:
            base_viewers = max(10, base_viewers + random.randint(-50, 60))
            sentiment = round(random.uniform(0.6, 0.95), 2)
            chat_rate = random.randint(10, 80)

            telemetry = {
                "timestamp": datetime.now().isoformat(),
                "concurrent_viewers": base_viewers,
                "chat_rate_per_min": chat_rate,
                "sentiment_ema": sentiment,
                "super_chats": round(random.random() * 5, 2) if random.random() > 0.8 else 0
            }
            yield telemetry
            time.sleep(1)

if __name__ == "__main__":
    engine = StreamPilotDataEngine(niche="tech")
    user_data = engine.fetch_layer3_data()
    print("\n--- Layer 4 Real-time Stream Test ---")
    stream = engine.stream_layer4_telemetry()
    for _ in range(5):
        print(next(stream))
