import sqlite3
import yfinance as yf
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
CORS(app)
app.secret_key = 'saas_secret_key_change_me'

# --- DATABASE CONFIGURATION ---
# Check if we are on Cloud (Postgres) or Local (SQLite)
IS_CLOUD = 'DATABASE_URL' in os.environ

def get_db():
    if IS_CLOUD:
        conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect('trading.db')
        conn.row_factory = sqlite3.Row
    return conn

def get_ph():
    """Returns the correct placeholder: %s for Postgres, ? for SQLite"""
    return '%s' if IS_CLOUD else '?'

# --- LOGIN CONFIG ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'home'

class User(UserMixin):
    def __init__(self, id, username, is_admin, family_id):
        self.id = id
        self.username = username
        self.is_admin = bool(is_admin)
        self.family_id = family_id

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    ph = get_ph()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM users WHERE id = {ph}', (user_id,))
    u = cursor.fetchone()
    conn.close()
    if u: return User(u['id'], u['username'], u['is_admin'], u['family_id'])
    return None

# --- AUTH ROUTES ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    ph = get_ph()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM users WHERE username = {ph}', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        user_obj = User(user['id'], user['username'], user['is_admin'], user['family_id'])
        login_user(user_obj)
        return jsonify({
            "message": "Logged in", 
            "username": user['username'],
            "is_admin": bool(user['is_admin'])
        })
    return jsonify({"error": "Wrong username or password"}), 401

@app.route('/api/register_family', methods=['POST'])
def register_family():
    data = request.get_json()
    family_name = data.get('family_name')
    username = data.get('username')
    password = data.get('password')
    ph = get_ph()
    
    if not family_name or not username or not password:
        return jsonify({"error": "Missing fields"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Create Family
    new_fam_id = str(uuid.uuid4())
    cursor.execute(f'INSERT INTO families (id, name) VALUES ({ph}, {ph})', (new_fam_id, family_name))
    
    # 2. Create Admin
    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
    try:
        cursor.execute(f'INSERT INTO users (family_id, username, password_hash, is_admin) VALUES ({ph}, {ph}, {ph}, {ph})', 
                      (new_fam_id, username, hashed_pw, 1))
    except Exception:
        return jsonify({"error": "Username already taken"}), 400
        
    # Handling ID retrieval for different databases
    if IS_CLOUD:
        cursor.execute(f"SELECT id FROM users WHERE username = {ph}", (username,))
        user_id = cursor.fetchone()['id']
    else:
        user_id = cursor.lastrowid

    # 3. Fund Account
    cursor.execute(f'INSERT INTO account (user_id, balance) VALUES ({ph}, {ph})', (user_id, 100000.00))
    
    conn.commit()
    conn.close()
    return jsonify({"message": "Family Created! Please Log In."})

@app.route('/api/logout')
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out"})

# --- CORE DATA ROUTES ---

@app.route('/api/balance')
@login_required
def get_balance():
    conn = get_db()
    ph = get_ph()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM account WHERE user_id = {ph}', (current_user.id,))
    acct = cursor.fetchone()
    conn.close()
    return jsonify({"balance": acct['balance']})

@app.route('/api/portfolio')
@login_required
def get_portfolio():
    conn = get_db()
    ph = get_ph()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM portfolio WHERE user_id = {ph}', (current_user.id,))
    rows = cursor.fetchall()
    conn.close()
    holdings = []
    
    for row in rows:
        try:
            # FIX: yfinance cache path for Render
            if IS_CLOUD: 
                if not os.path.exists('/tmp/py-yfinance'): os.makedirs('/tmp/py-yfinance')
                yf.set_tz_cache_location('/tmp/py-yfinance')
            
            price = yf.Ticker(row['ticker']).history(period="1d")['Close'].iloc[-1]
        except: 
            price = row['avg_price']
        
        val = price * row['shares']
        profit = val - (row['avg_price'] * row['shares'])
        
        holdings.append({
            "ticker": row['ticker'], "shares": row['shares'], 
            "current_price": round(price, 2), "market_value": round(val, 2), 
            "profit": round(profit, 2)
        })
    return jsonify(holdings)

@app.route('/api/quote')
@login_required
def get_quote():
    symbol = request.args.get('ticker')
    try:
        price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
        return jsonify({"ticker": symbol.upper(), "price": round(price, 2)})
    except: return jsonify({"error": "Symbol not found"}), 404

# --- TRADING ROUTES ---

@app.route('/api/buy', methods=['POST'])
@login_required
def buy():
    data = request.get_json()
    ticker = data.get('ticker').upper()
    shares = int(data.get('shares'))
    ph = get_ph()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try: price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except: return jsonify({"error": "Symbol not found"}), 404
    cost = price * shares
    
    cursor.execute(f'SELECT * FROM account WHERE user_id = {ph}', (current_user.id,))
    acct = cursor.fetchone()
    if acct['balance'] < cost:
        conn.close()
        return jsonify({"error": "Not enough money!"}), 400
        
    new_bal = acct['balance'] - cost
    cursor.execute(f'UPDATE account SET balance = {ph} WHERE user_id = {ph}', (new_bal, current_user.id))
    
    cursor.execute(f'SELECT * FROM portfolio WHERE ticker = {ph} AND user_id = {ph}', (ticker, current_user.id))
    holding = cursor.fetchone()
    
    if holding:
        cursor.execute(f'UPDATE portfolio SET shares = shares + {ph} WHERE id = {ph}', (shares, holding['id']))
    else:
        cursor.execute(f'INSERT INTO portfolio (user_id, ticker, shares, avg_price) VALUES ({ph}, {ph}, {ph}, {ph})', 
                       (current_user.id, ticker, shares, price))
                       
    cursor.execute(f'INSERT INTO transactions (user_id, type, ticker, shares, price) VALUES ({ph}, "BUY", {ph}, {ph}, {ph})',
                   (current_user.id, ticker, shares, price))
    
    conn.commit()
    conn.close()
    return jsonify({"message": f"Bought {shares} {ticker}!"})

@app.route('/api/sell', methods=['POST'])
@login_required
def sell():
    data = request.get_json()
    ticker = data.get('ticker').upper()
    shares = int(data.get('shares'))
    ph = get_ph()
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(f'SELECT * FROM portfolio WHERE ticker = {ph} AND user_id = {ph}', (ticker, current_user.id))
    holding = cursor.fetchone()
    
    if not holding or holding['shares'] < shares:
        conn.close()
        return jsonify({"error": "Not enough shares!"}), 400
        
    try: price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except: price = holding['avg_price']
    
    earnings = price * shares
    cursor.execute(f'SELECT * FROM account WHERE user_id = {ph}', (current_user.id,))
    acct = cursor.fetchone()
    cursor.execute(f'UPDATE account SET balance = {ph} WHERE user_id = {ph}', (acct['balance'] + earnings, current_user.id))
    
    if holding['shares'] == shares:
        cursor.execute(f'DELETE FROM portfolio WHERE id = {ph}', (holding['id'],))
    else:
        cursor.execute(f'UPDATE portfolio SET shares = shares - {ph} WHERE id = {ph}', (shares, holding['id']))
        
    cursor.execute(f'INSERT INTO transactions (user_id, type, ticker, shares, price) VALUES ({ph}, "SELL", {ph}, {ph}, {ph})',
                   (current_user.id, ticker, shares, price))
                   
    conn.commit()
    conn.close()
    return jsonify({"message": "Sold!"})

# --- RESEARCH & LEADERBOARD ---

@app.route('/api/leaderboard')
@login_required
def get_leaderboard():
    conn = get_db()
    ph = get_ph()
    cursor = conn.cursor()
    cursor.execute(f'SELECT id, username FROM users WHERE family_id = {ph}', (current_user.family_id,))
    users = cursor.fetchall()
    
    leaderboard = []
    for u in users:
        cursor.execute(f'SELECT balance FROM account WHERE user_id = {ph}', (u['id'],))
        cash = cursor.fetchone()['balance']
        
        cursor.execute(f'SELECT ticker, shares FROM portfolio WHERE user_id = {ph}', (u['id'],))
        portfolio = cursor.fetchall()
        stock_val = 0
        for p in portfolio:
            try:
                price = yf.Ticker(p['ticker']).history(period="1d")['Close'].iloc[-1]
                stock_val += price * p['shares']
            except: pass
            
        leaderboard.append({
            "username": u['username'], 
            "net_worth": round(cash + stock_val, 2),
            "cash": round(cash, 2), 
            "stocks": round(stock_val, 2)
        })
    conn.close()
    leaderboard.sort(key=lambda x: x['net_worth'], reverse=True)
    return jsonify(leaderboard)

@app.route('/api/research')
@login_required
def get_research():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM stock_ideas')
    rows = cursor.fetchall()
    conn.close()
    data = {}
    for row in rows:
        cat = row['category']
        if cat not in data: data[cat] = []
        data[cat].append({"ticker": row['ticker'], "name": row['name'], "desc": row['description']})
    return jsonify(data)

@app.route('/api/history')
@login_required
def get_history():
    conn = get_db()
    ph = get_ph()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM transactions WHERE user_id = {ph} ORDER BY id DESC', (current_user.id,))
    rows = cursor.fetchall()
    conn.close()
    history = []
    for row in rows:
        history.append({
            "type": row['type'], "ticker": row['ticker'], "shares": row['shares'],
            "price": row['price'], "date": str(row['timestamp'])
        })
    return jsonify(history)

# --- ADMIN ROUTES ---

@app.route('/api/admin/create_user', methods=['POST'])
@login_required
def create_family_member():
    if not current_user.is_admin: return jsonify({"error": "Admin Only!"}), 403
    
    data = request.get_json()
    new_username = data.get('username')
    new_password = data.get('password')
    starting_cash = float(data.get('cash', 1000.00))
    ph = get_ph()
    
    conn = get_db()
    cursor = conn.cursor()
    hashed_pw = generate_password_hash(new_password, method='pbkdf2:sha256')
    
    try:
        cursor.execute(f'INSERT INTO users (family_id, username, password_hash, is_admin) VALUES ({ph}, {ph}, {ph}, {ph})', 
                      (current_user.family_id, new_username, hashed_pw, 0))
    except Exception:
        return jsonify({"error": "Username already taken"}), 400
        
    if IS_CLOUD:
        cursor.execute(f"SELECT id FROM users WHERE username = {ph}", (new_username,))
        new_id = cursor.fetchone()['id']
    else:
        new_id = cursor.lastrowid

    cursor.execute(f'INSERT INTO account (user_id, balance) VALUES ({ph}, {ph})', (new_id, starting_cash))
    
    conn.commit()
    conn.close()
    return jsonify({"message": f"Added {new_username} to your family!"})

@app.route('/api/admin/reset', methods=['POST'])
@login_required
def admin_reset():
    if not current_user.is_admin: return jsonify({"error": "Admin Only!"}), 403
    data = request.get_json()
    start_amount = float(data.get('reset_amount', 10000))
    ph = get_ph()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f'SELECT id FROM users WHERE family_id = {ph}', (current_user.family_id,))
    users = cursor.fetchall()
    ids = [str(u['id']) for u in users]
    
    if not ids: return jsonify({"error": "No users found"}), 404
    
    id_list = ",".join(ids)
    
    # Using format strings for the ID list (safe here because IDs come from DB)
    cursor.execute(f'UPDATE account SET balance = {ph} WHERE user_id IN ({id_list})', (start_amount,)) 
    cursor.execute(f'DELETE FROM portfolio WHERE user_id IN ({id_list})')
    cursor.execute(f'DELETE FROM transactions WHERE user_id IN ({id_list})')
    
    conn.commit()
    conn.close()
    return jsonify({"message": f"Game Reset! Everyone starts with ${start_amount:,.2f}"})

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5002)