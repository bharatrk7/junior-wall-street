import time
import requests
import os
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- CONFIGURATION ---
# The Bot looks for the 'API_URL' environment variable. 
DEFAULT_URL = "http://127.0.0.1:5002/api"
API_URL = os.environ.get('API_URL', DEFAULT_URL)

# DEBUG: Print where we are trying to connect so we can see it in logs
print(f"DEBUG: Configured API_URL is: {API_URL}")

NEWS_API_KEY = os.environ.get('NEWS_API_KEY', "PASTE_YOUR_NEWSAPI_KEY_HERE")
BOT_USERNAME = os.environ.get('BOT_USERNAME', "Terminator")
BOT_PASSWORD = os.environ.get('BOT_PASSWORD', "password123")

HYPE_THRESHOLD = 0.2   
PANIC_THRESHOLD = -0.2 
MAX_SPEND_PCT = 0.10   

analyzer = SentimentIntensityAnalyzer()

def login():
    session = requests.Session()
    try:
        print(f"🤖 Connecting to {API_URL} as {BOT_USERNAME}...")
        res = session.post(f"{API_URL}/login", json={"username": BOT_USERNAME, "password": BOT_PASSWORD})
        if res.status_code == 200:
            print(f"✅ Bot Login Successful")
            return session
        print(f"❌ Login Failed: {res.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")
    return None

def get_market_universe(session):
    print("📋 Fetching stock list...")
    try:
        res = session.get(f"{API_URL}/research")
        if res.status_code != 200: return []
        data = res.json()
        tickers = []
        for category, items in data.items():
            for item in items:
                tickers.append(item['ticker'])
        print(f"✅ Monitoring {len(tickers)} stocks: {tickers[:3]}...")
        return tickers
    except:
        return []

def check_news_sentiment(ticker):
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
        return total_score / len(articles)
    except Exception as e:
        print(f"Error: {e}")
        return 0

def execute_strategy(session, ticker, sentiment):
    try:
        bal_res = session.get(f"{API_URL}/balance")
        if bal_res.status_code != 200: return
        cash = bal_res.json()['balance']
        
        quote_res = session.get(f"{API_URL}/quote?ticker={ticker}")
        if quote_res.status_code != 200: return
        price = quote_res.json()['price']
        
        if sentiment > HYPE_THRESHOLD:
            budget = cash * MAX_SPEND_PCT
            shares_to_buy = int(budget // price)
            if shares_to_buy > 0:
                print(f"   🚀 POSITIVE ({sentiment:.2f})! Buying {shares_to_buy} shares...")
                res = session.post(f"{API_URL}/buy", json={"ticker": ticker, "shares": shares_to_buy})
                if res.status_code == 200: print(f"   ✅ EXECUTED BUY.")
                else: print(f"   ❌ FAILED: {res.text}")
        
        elif sentiment < PANIC_THRESHOLD:
            print(f"   📉 NEGATIVE ({sentiment:.2f})! Selling...")
            res = session.post(f"{API_URL}/sell", json={"ticker": ticker, "shares": 5})
            if res.status_code == 200: print(f"   ✅ EXECUTED SELL.")
            
    except Exception as e:
        print(f"Trade Error: {e}")

if __name__ == "__main__":
    while True:
        session = login()
        if session:
            tickers = get_market_universe(session)
            if not tickers: tickers = ['AAPL', 'TSLA']
            for ticker in tickers:
                sentiment = check_news_sentiment(ticker)
                if abs(sentiment) > 0.05: execute_strategy(session, ticker, sentiment)
                time.sleep(5)
            print("--- Resting... ---")
            time.sleep(600)
        else:
            print("Login failed. Retrying in 60s...")
            time.sleep(60)