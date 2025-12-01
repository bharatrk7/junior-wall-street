import time
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:5002/api"  # Your App URL

# ---------------------------------------------------------
# PASTE YOUR KEY BELOW
# ---------------------------------------------------------
NEWS_API_KEY = "8b4ef3ceafbc4958b967a5ded2ad7182" 
# ---------------------------------------------------------

# Bot Credentials (Must match what is in your database!)
BOT_USERNAME = "Kesavan_testbot"
BOT_PASSWORD = "123"

# Trading Settings
HYPE_THRESHOLD = 0.2   # Sentiment needed to buy (0.0 to 1.0)
PANIC_THRESHOLD = -0.2 # Sentiment needed to sell (-1.0 to 0.0)
MAX_SPEND_PCT = 0.10   # Only spend 10% of available cash per trade

analyzer = SentimentIntensityAnalyzer()

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

def get_market_universe(session):
    """Ask the App what stocks are available in the Research tab."""
    print("📋 Fetching stock list from Research Tab...")
    res = session.get(f"{API_URL}/research")
    if res.status_code != 200: return []
    
    data = res.json()
    tickers = []
    # Research data is grouped by category {"Tech": [..], "Food": [..]}
    for category, items in data.items():
        for item in items:
            tickers.append(item['ticker'])
    
    print(f"✅ Monitoring {len(tickers)} stocks: {', '.join(tickers[:5])}...")
    return tickers

def check_news_sentiment(ticker):
    """Ask NewsAPI for real headlines about a stock."""
    # We sort by 'publishedAt' to get the freshest news
    url = f"https://newsapi.org/v2/everything?q={ticker}&language=en&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
    try:
        res = requests.get(url).json()
        if res.get('status') != 'ok': 
            return 0
        
        articles = res.get('articles', [])
        if not articles: return 0
        
        total_score = 0
        print(f"\n📰 Scanning News for {ticker}:")
        for a in articles:
            # Analyze Title
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
    # 1. Check Balance
    bal_res = session.get(f"{API_URL}/balance")
    if bal_res.status_code != 200: return
    cash = bal_res.json()['balance']
    
    # 2. Get Stock Price
    quote_res = session.get(f"{API_URL}/quote?ticker={ticker}")
    if quote_res.status_code != 200: return
    price = quote_res.json()['price']
    
    # --- BUY LOGIC ---
    if sentiment > HYPE_THRESHOLD:
        # Smart Sizing: Spend 10% of current cash
        budget = cash * MAX_SPEND_PCT
        shares_to_buy = int(budget // price)
        
        if shares_to_buy > 0:
            print(f"   🚀 POSITIVE SENTIMENT ({sentiment:.2f})! Budget: ${budget:.2f}. Buying {shares_to_buy} shares...")
            res = session.post(f"{API_URL}/buy", json={"ticker": ticker, "shares": shares_to_buy})
            if res.status_code == 200: print(f"   ✅ EXECUTED BUY.")
            else: print(f"   ❌ FAILED: {res.text}")
        else:
            print(f"   ⚠️ Good news, but not enough cash to buy {ticker} at ${price}")
    
    # --- SELL LOGIC ---
    elif sentiment < PANIC_THRESHOLD:
        print(f"   📉 NEGATIVE SENTIMENT ({sentiment:.2f})! Panic Selling...")
        # Sell a fixed amount to be safe
        res = session.post(f"{API_URL}/sell", json={"ticker": ticker, "shares": 5})
        if res.status_code == 200: print(f"   ✅ EXECUTED SELL.")

if __name__ == "__main__":
    session = login()
    if session:
        # 1. Get the list of stocks your kids trade
        tickers = get_market_universe(session)
        
        if not tickers:
            print("⚠️ No stocks found in Research tab. Using default list.")
            tickers = ['AAPL', 'TSLA', 'DIS', 'RBLX', 'NKE']

        print("⚡ BOT ACTIVE. Press Ctrl+C to stop.")
        
        while True:
            # Cycle through every stock in the list
            for ticker in tickers:
                sentiment = check_news_sentiment(ticker)
                
                if abs(sentiment) > 0.05: # Only print/act if there is actual sentiment
                    execute_strategy(session, ticker, sentiment)
                
                # IMPORTANT: Free NewsAPI limits to 100 reqs/day. 
                # We sleep to prevent burning your key in 5 minutes.
                time.sleep(5) 
            
            print("--- Cycle Complete. Resting... ---")
            time.sleep(600)