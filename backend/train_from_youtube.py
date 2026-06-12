import os
import sys
import time
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# Import our existing YouTube connection
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from youtube_api import YouTubeConnection

print("🚀 Initializing YouTube API Live Scraper & Training Pipeline...")

# 1. Connect to YouTube
yt = YouTubeConnection()
try:
    yt.authenticate()
except Exception as e:
    print(f"❌ Failed to authenticate: {e}")

if not yt.youtube:
    print("❌ Cannot connect to YouTube API. Exiting.")
    sys.exit(1)

print("✅ Connected to YouTube API.")

# 2. Scrape Live Data
NICHE_QUERY = "gaming pc build"
MAX_RESULTS = 50 # Keep it small to avoid API quota limits for this demo
print(f"📡 Searching YouTube for top {MAX_RESULTS} trending videos in '{NICHE_QUERY}'...")

try:
    search_response = yt.youtube.search().list(
        q=NICHE_QUERY,
        part="id,snippet",
        maxResults=MAX_RESULTS,
        type="video",
        order="relevance" # Gets the most relevant/trending ones
    ).execute()

    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

    print(f"📥 Found {len(video_ids)} videos. Fetching detailed statistics...")

    # Get statistics for all found videos
    stats_response = yt.youtube.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids)
    ).execute()

    # 3. Process the Data
    dataset = []
    power_words = ["ultimate", "destroy", "banned", "secret", "truth", "insane", "best", "worst", "cheap", "budget"]
    negative_hooks = ["don't", "stop", "regret", "never", "hate", "scam", "mistake"]

    for item in stats_response.get('items', []):
        title = item['snippet']['title']
        views = int(item['statistics'].get('viewCount', 0))
        likes = int(item['statistics'].get('likeCount', 0))

        # Calculate our ML Features
        t_len = len(title)
        c_ratio = sum(1 for c in title if c.isupper()) / t_len if t_len > 0 else 0
        has_power = 1 if any(w in title.lower() for w in power_words) else 0
        has_neg = 1 if any(w in title.lower() for w in negative_hooks) else 0

        # We don't have exact CTR from the public API, so we infer success based on Views & Like Ratio
        # A highly successful video will have high views and high engagement
        engagement_score = (likes / views * 100) if views > 0 else 0
        # We synthesize a "Proxy CTR" score from 1 to 15 based on view velocity and engagement
        proxy_ctr = np.clip(np.log10(views + 1) + (engagement_score * 0.5), 1.0, 15.0)

        dataset.append({
            'title': title,
            'title_length': t_len,
            'caps_ratio': c_ratio,
            'has_power_word': has_power,
            'has_negative_hook': has_neg,
            'views': views,
            'likes': likes,
            'proxy_ctr': proxy_ctr
        })

    df = pd.DataFrame(dataset)
    print("\n📊 First 3 Scraped Videos:")
    print(df[['title', 'views', 'proxy_ctr']].head(3))

    # 4. Train the Niche Model
    print("\n🧠 Training Niche Intelligence Model on LIVE YouTube Data...")

    # We add thumbnail mock data to keep the model shape identical to our base model
    X = df[['title_length', 'caps_ratio', 'has_power_word', 'has_negative_hook']]
    X['thumbnail_contrast'] = np.random.randint(40, 80, len(df))
    X['face_prominence'] = np.random.randint(30, 70, len(df))

    y = df['proxy_ctr']

    # Since dataset is small, we train on everything
    model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
    model.fit(X, y)

    # 5. Save the Model
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, 'niche_intelligence_rf.pkl')

    joblib.dump(model, model_path)
    print(f"\n✅ SUCCESS! Trained on real YouTube API data.")
    print(f"💾 Niche Model saved to: {model_path}")

except Exception as e:
    print(f"❌ Error during scraping/training: {e}")
