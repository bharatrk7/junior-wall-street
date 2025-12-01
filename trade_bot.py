import time
import requests
import os
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- CONFIGURATION ---
# Default to Localhost (Port 5002) if no Cloud URL is found
DEFAULT_URL = "http://127.0.0.1:5002/api"
API_URL = os.environ.get('API_URL', DEFAULT_URL)

print(f"DEBUG: Connecting to: {API_URL}")

# ---------------------------------------------------------
# 👇 UPDATED CREDENTIALS 👇
# ---------------------------------------------------------
# This must match the user you created in the 'Dad Zone'
BOT_USERNAME = os.environ.get('BOT_USERNAME', "Kesavan_AI_Bot")
BOT_PASSWORD = os.environ.get('BOT_PASSWORD', "67")

# NEWS API KEY
# Replace the string below with your actual key if running locally
NEWS_API_KEY = os.environ.get('NEWS_API_KEY', "PASTE_YOUR_NEWSAPI_KEY_HERE")

# Trading Settings
HYPE_THRESHOLD = 0.2   # Buy if sentiment > 0.2
PANIC_THRESHOLD = -0.2 # Sell if sentiment < -0.2
MAX_SPEND_PCT = 0.10   # Spend 10% of cash per trade

analyzer = SentimentIntensityAnalyzer()

def login():
    session = requests.Session()
    try:
        print(f"🤖 Logging in as '{BOT_USERNAME}'...")
        res = session.post(f"{API_URL}/login", json={"username": BOT_USERNAME, "password": BOT_PASSWORD})
        
        if res.status_code == 200:
            print(f"✅ SUCCESS: Bot logged in!")
            return session
        else:
            print(f"❌ LOGIN FAILED: {res.text}")
            print(f"   (Double check that '{BOT_USERNAME}' exists in your Family Admin panel!)")
            return None
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print("   (Is the server running?)")
    return None

def get_market_universe(session):
    """Ask the App what stocks are available in the Research tab."""
    print("📋 Fetching stock list from Research Tab...")
    try:
        res = session.get(f"{API_URL}/research")
        if res.status_code != 200: return []
        
        data = res.json()
        tickers = []
        # Research data is grouped by category
        for category, items in data.items():
            for item in items:
                tickers.append(item['ticker'])
        
        print(f"✅ Monitoring {len(tickers)} stocks: {tickers[:3]}...")
        return tickers
    except:
        return []

def check_news_sentiment(ticker):
    """Ask NewsAPI for real headlines about a stock."""
    url = f"https://newsapi.org/v2/everything?q={ticker}&language=en&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
    try:
        res = requests.get(url).json()
        if res.get('status') != 'ok': return 0
        
        articles = res.get('articles', [])
        if not articles: return 0
        
        total_score = 0
        print(f"\n📰 News for {ticker}:")
        for a in articles:
            text = a['title']
            score = analyzer.polarity_scores(text)['compound']
            total_score += score
            print(f"   - {text[:60]}... (Score: {score:.2f})")
            
        avg_score = total_score / len(articles)
        return avg_score
    except Exception as e:
        print(f"Error fetching news: {e}")
        return 0

def execute_strategy(session, ticker, sentiment):
    try:
        # 1. Check Cash
        bal_res = session.get(f"{API_URL}/balance")
        if bal_res.status_code != 200: return
        cash = bal_res.json()['balance']
        
        # 2. Check Price
        quote_res = session.get(f"{API_URL}/quote?ticker={ticker}")
        if quote_res.status_code != 200: return
        price = quote_res.json()['price']
        
        # --- BUY LOGIC ---
        if sentiment > HYPE_THRESHOLD:
            budget = cash * MAX_SPEND_PCT
            shares_to_buy = int(budget // price)
            
            if shares_to_buy > 0:
                print(f"   🚀 POSITIVE ({sentiment:.2f})! Buying {shares_to_buy} shares...")
                res = session.post(f"{API_URL}/buy", json={"ticker": ticker, "shares": shares_to_buy})
                if res.status_code == 200: 
                    print(f"   ✅ EXECUTED BUY.")
                else: 
                    print(f"   ❌ FAILED: {res.text}")
            else:
                print(f"   ⚠️ Good news, but not enough cash to buy {ticker}")
        
        # --- SELL LOGIC ---
        elif sentiment < PANIC_THRESHOLD:
            print(f"   📉 NEGATIVE ({sentiment:.2f})! Selling...")
            # Simple logic: Try to sell 5 shares
            res = session.post(f"{API_URL}/sell", json={"ticker": ticker, "shares": 5})
            if res.status_code == 200: 
                print(f"   ✅ EXECUTED SELL.")
            
    except Exception as e:
        print(f"Trade Error: {e}")

if __name__ == "__main__":
    while True:
        session = login()
        if session:
            # 1. Get List
            tickers = get_market_universe(session)
            if not tickers: 
                print("⚠️ No stocks found. Defaulting to AAPL/TSLA.")
                tickers = ['AAPL', 'TSLA']

            print("⚡ BOT ACTIVE. Press Ctrl+C to stop.")
            
            # 2. Scan and Trade
            for ticker in tickers:
                sentiment = check_news_sentiment(ticker)
                
                # Only trade if sentiment is significant
                if abs(sentiment) > 0.05: 
                    execute_strategy(session, ticker, sentiment)
                
                # Sleep to respect API limits
                time.sleep(5) 
            
            print("--- Cycle Complete. Resting for 10 minutes... ---")
            time.sleep(600)
        else:
            print("Login failed. Retrying in 60s...")
            time.sleep(60)