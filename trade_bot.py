import time
import requests
import os
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- CONFIGURATION ---
DEFAULT_URL = "http://127.0.0.1:5002/api"
API_URL = os.environ.get('API_URL', DEFAULT_URL)

BOT_USERNAME = os.environ.get('BOT_USERNAME', "Kesavan_AI_Bot")
BOT_PASSWORD = os.environ.get('BOT_PASSWORD', "123")
NEWS_API_KEY = os.environ.get('NEWS_API_KEY', "PASTE_YOUR_NEWSAPI_KEY_HERE")

# --- HYPERACTIVE MODE ---
HYPE_THRESHOLD = 0.01   # Buy if score is > 0.01 (Almost anything positive)
PANIC_THRESHOLD = -0.01 # Sell if score is < -0.01 (Almost anything negative)
MAX_SPEND_PCT = 0.10

analyzer = SentimentIntensityAnalyzer()

def login():
    session = requests.Session()
    try:
        print(f"🤖 Connecting to {API_URL} as {BOT_USERNAME}...")
        res = session.post(f"{API_URL}/login", json={"username": BOT_USERNAME, "password": BOT_PASSWORD})
        if res.status_code == 200:
            print(f"✅ SUCCESS: Bot logged in!")
            return session
        else:
            print(f"❌ LOGIN FAILED: {res.text}")
            return None
    except Exception as e:
        print(f"❌ Connection Error: {e}")
    return None

def get_market_universe(session):
    try:
        res = session.get(f"{API_URL}/research")
        if res.status_code != 200: return []
        data = res.json()
        tickers = []
        for category, items in data.items():
            for item in items:
                tickers.append(item['ticker'])
        print(f"📋 Monitoring {len(tickers)} stocks from Research Tab.")
        return tickers
    except:
        return []

def check_news_sentiment(ticker):
    url = f"https://newsapi.org/v2/everything?q={ticker}&language=en&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
    try:
        res = requests.get(url).json()
        if res.get('status') != 'ok': 
            print(f"   ⚠️ NewsAPI Error for {ticker}: {res.get('message')}")
            return 0
        
        articles = res.get('articles', [])
        if not articles: 
            print(f"   📭 No news found for {ticker}")
            return 0
        
        total_score = 0
        # Print the headline so we know it's reading!
        print(f"   📰 Read: {articles[0]['title'][:50]}...")
        
        for a in articles:
            text = a['title']
            score = analyzer.polarity_scores(text)['compound']
            total_score += score
            
        return total_score / len(articles)
    except Exception as e:
        print(f"Error: {e}")
        return 0

def execute_strategy(session, ticker, sentiment):
    # 1. Print the decision logic
    print(f"   🧐 Analyzed {ticker}: Score is {sentiment:.3f}")

    if abs(sentiment) < 0.01:
        print(f"   😴 Boring news. Skipping.")
        return

    # 2. Check Cash
    bal_res = session.get(f"{API_URL}/balance")
    if bal_res.status_code != 200: return
    cash = bal_res.json()['balance']
    
    # 3. Get Price
    quote_res = session.get(f"{API_URL}/quote?ticker={ticker}")
    if quote_res.status_code != 200: return
    price = quote_res.json()['price']
    
    # 4. Trade
    if sentiment > HYPE_THRESHOLD:
        budget = cash * MAX_SPEND_PCT
        shares_to_buy = int(budget // price)
        if shares_to_buy > 0:
            print(f"   🚀 POSITIVE! Buying {shares_to_buy} shares...")
            res = session.post(f"{API_URL}/buy", json={"ticker": ticker, "shares": shares_to_buy})
            if res.status_code == 200: print(f"   ✅ EXECUTED BUY.")
            else: print(f"   ❌ FAILED: {res.text}")
        else:
            print(f"   ⚠️ Not enough cash to buy {ticker}")
    
    elif sentiment < PANIC_THRESHOLD:
        print(f"   📉 NEGATIVE! Selling...")
        res = session.post(f"{API_URL}/sell", json={"ticker": ticker, "shares": 5})
        if res.status_code == 200: print(f"   ✅ EXECUTED SELL.")

if __name__ == "__main__":
    while True:
        session = login()
        if session:
            tickers = get_market_universe(session)
            if not tickers: tickers = ['AAPL', 'TSLA']
            
            for ticker in tickers:
                sentiment = check_news_sentiment(ticker)
                execute_strategy(session, ticker, sentiment)
                time.sleep(2) # Short pause between stocks
            
            print("--- Cycle Complete. Resting... ---")
            time.sleep(600)
        else:
            print("Login failed. Retrying in 60s...")
            time.sleep(60)