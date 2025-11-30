import sqlite3
import yfinance as yf
import uuid
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
CORS(app)
app.secret_key = 'saas_secret_key_change_me' # In production, hide this!

# --- LOGIN CONFIG ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'home'

def get_db():
    conn = sqlite3.connect('trading.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- USER MODEL ---
class User(UserMixin):
    def __init__(self, id, username, is_admin, family_id):
        self.id = id
        self.username = username
        self.is_admin = bool(is_admin)
        self.family_id = family_id

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    u = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if u: return User(u['id'], u['username'], u['is_admin'], u['family_id'])
    return None

# --- AUTH ROUTES ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db()
    # In a real SaaS, we would also check Family ID or Email to ensure uniqueness
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
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
    # Public Sign Up: Creates Family + Admin User
    data = request.get_json()
    family_name = data.get('family_name')
    username = data.get('username')
    password = data.get('password')
    
    if not family_name or not username or not password:
        return jsonify({"error": "Missing fields"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Create Family
    new_fam_id = str(uuid.uuid4())
    cursor.execute('INSERT INTO families (id, name) VALUES (?, ?)', (new_fam_id, family_name))
    
    # 2. Create Admin
    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
    try:
        cursor.execute('INSERT INTO users (family_id, username, password_hash, is_admin) VALUES (?, ?, ?, ?)', 
                      (new_fam_id, username, hashed_pw, 1))
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already taken"}), 400
        
    # 3. Fund Account
    user_id = cursor.lastrowid
    cursor.execute('INSERT INTO account (user_id, balance) VALUES (?, ?)', (user_id, 100000.00))
    
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
    acct = conn.execute('SELECT * FROM account WHERE user_id = ?', (current_user.id,)).fetchone()
    conn.close()
    return jsonify({"balance": acct['balance']})

@app.route('/api/portfolio')
@login_required
def get_portfolio():
    conn = get_db()
    rows = conn.execute('SELECT * FROM portfolio WHERE user_id = ?', (current_user.id,)).fetchall()
    conn.close()
    holdings = []
    
    # Live Pricing Loop
    for row in rows:
        try:
            price = yf.Ticker(row['ticker']).history(period="1d")['Close'].iloc[-1]
        except: 
            price = row['avg_price'] # Safety net
        
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
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Get Price
    try: price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except: return jsonify({"error": "Symbol not found"}), 404
    cost = price * shares
    
    # 2. Check Funds
    acct = cursor.execute('SELECT * FROM account WHERE user_id = ?', (current_user.id,)).fetchone()
    if acct['balance'] < cost:
        conn.close()
        return jsonify({"error": "Not enough money!"}), 400
        
    # 3. Execute
    new_bal = acct['balance'] - cost
    cursor.execute('UPDATE account SET balance = ? WHERE user_id = ?', (new_bal, current_user.id))
    
    holding = cursor.execute('SELECT * FROM portfolio WHERE ticker = ? AND user_id = ?', (ticker, current_user.id)).fetchone()
    if holding:
        cursor.execute('UPDATE portfolio SET shares = shares + ? WHERE id = ?', (shares, holding['id']))
    else:
        cursor.execute('INSERT INTO portfolio (user_id, ticker, shares, avg_price) VALUES (?, ?, ?, ?)', 
                       (current_user.id, ticker, shares, price))
                       
    cursor.execute('INSERT INTO transactions (user_id, type, ticker, shares, price) VALUES (?, "BUY", ?, ?, ?)',
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
    
    conn = get_db()
    cursor = conn.cursor()
    
    holding = cursor.execute('SELECT * FROM portfolio WHERE ticker = ? AND user_id = ?', (ticker, current_user.id)).fetchone()
    if not holding or holding['shares'] < shares:
        conn.close()
        return jsonify({"error": "Not enough shares!"}), 400
        
    try: price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except: price = holding['avg_price']
    
    earnings = price * shares
    acct = cursor.execute('SELECT * FROM account WHERE user_id = ?', (current_user.id,)).fetchone()
    cursor.execute('UPDATE account SET balance = ? WHERE user_id = ?', (acct['balance'] + earnings, current_user.id))
    
    if holding['shares'] == shares:
        cursor.execute('DELETE FROM portfolio WHERE id = ?', (holding['id'],))
    else:
        cursor.execute('UPDATE portfolio SET shares = shares - ? WHERE id = ?', (shares, holding['id']))
        
    cursor.execute('INSERT INTO transactions (user_id, type, ticker, shares, price) VALUES (?, "SELL", ?, ?, ?)',
                   (current_user.id, ticker, shares, price))
                   
    conn.commit()
    conn.close()
    return jsonify({"message": "Sold!"})

# --- RESEARCH & LEADERBOARD (Family Filtered) ---

@app.route('/api/leaderboard')
@login_required
def get_leaderboard():
    conn = get_db()
    # Filter by YOUR family ID
    users = conn.execute('SELECT id, username FROM users WHERE family_id = ?', (current_user.family_id,)).fetchall()
    
    leaderboard = []
    for u in users:
        cash = conn.execute('SELECT balance FROM account WHERE user_id = ?', (u['id'],)).fetchone()['balance']
        portfolio = conn.execute('SELECT ticker, shares FROM portfolio WHERE user_id = ?', (u['id'],)).fetchall()
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
    rows = conn.execute('SELECT * FROM stock_ideas').fetchall()
    conn.close()
    data = {}
    for row in rows:
        cat = row['category']
        if cat not in data: data[cat] = []
        data[cat].append({"ticker": row['ticker'], "name": row['name'], "desc": row['description']})
    return jsonify(data)

# --- ADMIN ROUTES (Dad Zone) ---

@app.route('/api/admin/create_user', methods=['POST'])
@login_required
def create_family_member():
    if not current_user.is_admin: return jsonify({"error": "Admin Only!"}), 403
    
    data = request.get_json()
    new_username = data.get('username')
    new_password = data.get('password')
    starting_cash = float(data.get('cash', 1000.00))
    
    conn = get_db()
    cursor = conn.cursor()
    hashed_pw = generate_password_hash(new_password, method='pbkdf2:sha256')
    
    try:
        # Create user in CURRENT USER'S family
        cursor.execute('INSERT INTO users (family_id, username, password_hash, is_admin) VALUES (?, ?, ?, ?)', 
                      (current_user.family_id, new_username, hashed_pw, 0))
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already taken"}), 400
        
    new_id = cursor.lastrowid
    cursor.execute('INSERT INTO account (user_id, balance) VALUES (?, ?)', (new_id, starting_cash))
    
    conn.commit()
    conn.close()
    return jsonify({"message": f"Added {new_username} to your family!"})

@app.route('/api/admin/reset', methods=['POST'])
@login_required
def admin_reset():
    if not current_user.is_admin: return jsonify({"error": "Admin Only!"}), 403
    
    data = request.get_json()
    start_amount = float(data.get('reset_amount', 10000)) # Flexible Amount
    
    conn = get_db()
    # Find all users in YOUR family
    users = conn.execute('SELECT id FROM users WHERE family_id = ?', (current_user.family_id,)).fetchall()
    ids = [str(u['id']) for u in users]
    
    if not ids: return jsonify({"error": "No users found"}), 404
    
    id_list = ",".join(ids)
    cursor = conn.cursor()
    
    # Reset Accounts & Wipe Data
    cursor.execute(f'UPDATE account SET balance = ? WHERE user_id IN ({id_list})', (start_amount,)) 
    cursor.execute(f'DELETE FROM portfolio WHERE user_id IN ({id_list})')
    cursor.execute(f'DELETE FROM transactions WHERE user_id IN ({id_list})')
    
    conn.commit()
    conn.close()
    return jsonify({"message": f"Game Reset! Everyone starts with ${start_amount:,.2f}"})

# --- STATIC FILE SERVER ---
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5002)