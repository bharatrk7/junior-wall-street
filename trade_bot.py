import time
import requests
import random
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:5002/api"

# CRITICAL: This must match 'setup_bot_user.py' exactly
BOT_USERNAME = "The_Terminator" 
BOT_PASSWORD = "password123"

WATCHLIST = ['AAPL', 'TSLA', 'NVDA', 'RBLX', 'MCD']
analyzer = SentimentIntensityAnalyzer()

# --- FAKE NEWS GENERATOR ---
fake_posts = [
    {"title": "TSLA is going to the moon!", "body": "I love Elon.", "score": 5000, "ticker": "TSLA"},
    {"title": "AAPL is dead money", "body": "Selling everything.", "score": 200, "ticker": "AAPL"},
    {"title": "RBLX earnings were amazing", "body": "Kids are addicted.", "score": 1000, "ticker": "RBLX"},
    {"title": "NVDA AI revolution", "body": "Buying every dip.", "score": 8000, "ticker": "NVDA"},
]

def login():
    session = requests.Session()
    try:
        print(f"🤖 Connecting to {API_URL}...")
        res = session.post(f"{API_URL}/login", json={"username": BOT_USERNAME, "password": BOT_PASSWORD})
        if res.status_code == 200:
            print(f"✅ Bot Login Successful as {BOT_USERNAME}")
            return session
        print(f"❌ Login Failed: {res.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")
    return None

def run_bot(session):
    print(f"\n🔎 Scanning Market...")
    post = random.choice(fake_posts) # Pick random news
    print(f"   NEWS: '{post['title']}'")
    
    sentiment = analyzer.polarity_scores(post['title'])['compound']
    score = sentiment * (post['score'] / 100)
    
    if score > 5:
        print(f"   🚀 HIGH HYPE for {post['ticker']}! Buying...")
        res = session.post(f"{API_URL}/buy", json={"ticker": post['ticker'], "shares": 10})
        if res.status_code == 200:
            print(f"   ✅ EXECUTED: Bought 10 {post['ticker']}")
            
            # --- VERIFICATION ---
            bal_res = session.get(f"{API_URL}/balance")
            if bal_res.status_code == 200:
                cash = bal_res.json().get('balance')
                print(f"   💰 Remaining Cash: ${cash:,.2f}")
            
        else:
            print(f"   ❌ FAILED: {res.text}")
    else:
        print(f"   😴 Sentiment too low for {post['ticker']}. Waiting...")

if __name__ == "__main__":
    session = login()
    if session:
        while True:
            run_bot(session)
            time.sleep(5) # Run every 5 seconds