import sqlite3
from werkzeug.security import generate_password_hash
import uuid

connection = sqlite3.connect('trading.db')
cursor = connection.cursor()

# 1. FAMILIES
cursor.execute('''
    CREATE TABLE IF NOT EXISTS families (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
''')

# 2. USERS
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id TEXT NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin BOOLEAN DEFAULT 0,
        FOREIGN KEY (family_id) REFERENCES families (id),
        UNIQUE(family_id, username)
    )
''')

# 3. ACCOUNT
cursor.execute('''
    CREATE TABLE IF NOT EXISTS account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        balance REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

# 4. PORTFOLIO
cursor.execute('''
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        shares INTEGER NOT NULL,
        avg_price REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

# 5. TRANSACTIONS
cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        ticker TEXT NOT NULL,
        shares INTEGER NOT NULL,
        price REAL NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

# 6. STOCK IDEAS (The Research List)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        ticker TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT
    )
''')

# --- EXPANDED SEED DATA (35+ Stocks) ---
stock_list = [
    # VIDEO GAMES
    ('Video Games', 'RBLX', 'Roblox', 'The platform where you build and play games.'),
    ('Video Games', 'NTDOY', 'Nintendo', 'Mario, Zelda, Pokemon, and the Switch.'),
    ('Video Games', 'EA', 'Electronic Arts', 'FIFA, Madden, and The Sims.'),
    ('Video Games', 'TTWO', 'Take-Two', 'Grand Theft Auto and NBA 2K.'),
    ('Video Games', 'MSFT', 'Microsoft (Xbox)', 'Xbox, Minecraft, and Windows computers.'),
    ('Video Games', 'SONY', 'Sony', 'PlayStation consoles and games.'),

    # SOCIAL MEDIA & APPS
    ('Social Media', 'SNAP', 'Snapchat', 'Filters, streaks, and messaging.'),
    ('Social Media', 'META', 'Meta', 'Instagram, Facebook, and WhatsApp.'),
    ('Social Media', 'RDDT', 'Reddit', 'The front page of the internet.'),
    ('Social Media', 'PINS', 'Pinterest', 'Ideas, styles, and mood boards.'),
    ('Social Media', 'SPOT', 'Spotify', 'Music and podcast streaming.'),
    ('Social Media', 'UBER', 'Uber', 'Rides and food delivery.'),

    # FOOD & DRINK
    ('Snacks & Food', 'MCD', 'McDonalds', 'Big Macs, Fries, and Happy Meals.'),
    ('Snacks & Food', 'DPZ', 'Domino\'s', 'Pizza delivery technology.'),
    ('Snacks & Food', 'SBUX', 'Starbucks', 'Coffee, Cake Pops, and Frappuccinos.'),
    ('Snacks & Food', 'KO', 'Coca-Cola', 'Coke, Sprite, and Dasani Water.'),
    ('Snacks & Food', 'PEP', 'PepsiCo', 'Pepsi, Gatorade, Doritos, and Cheetos.'),
    ('Snacks & Food', 'YUM', 'Yum! Brands', 'Taco Bell, KFC, and Pizza Hut.'),
    ('Snacks & Food', 'HSY', 'Hershey', 'Chocolate bars, Reese\'s, and Kisses.'),

    # SHOPPING
    ('Shopping', 'AMZN', 'Amazon', 'Fast delivery, Prime Video, and Alexa.'),
    ('Shopping', 'WMT', 'Walmart', 'Superstores and grocery shopping.'),
    ('Shopping', 'TGT', 'Target', 'The store with the red bullseye dog.'),
    ('Shopping', 'COST', 'Costco', 'Huge warehouse stores and $1.50 hot dogs.'),
    ('Shopping', 'EBAY', 'eBay', 'Buying and selling collectibles online.'),

    # CLOTHES & SHOES
    ('Fashion', 'NKE', 'Nike', 'Air Jordans, sneakers, and sports gear.'),
    ('Fashion', 'CROX', 'Crocs', 'Foam clogs and Jibbitz charms.'),
    ('Fashion', 'LULU', 'Lululemon', 'Yoga pants and athletic wear.'),
    ('Fashion', 'SKX', 'Skechers', 'Comfortable shoes and sneakers.'),
    ('Fashion', 'TJX', 'TJ Maxx', 'Discount clothing and home goods.'),

    # ENTERTAINMENT
    ('Entertainment', 'DIS', 'Disney', 'Marvel, Star Wars, Pixar, and Theme Parks.'),
    ('Entertainment', 'NFLX', 'Netflix', 'Streaming movies and Stranger Things.'),
    ('Entertainment', 'CNK', 'Cinemark', 'Movie theaters and popcorn.'),
    ('Entertainment', 'CMCSA', 'Comcast/Universal', 'Minions, Mario Movie, and Universal Studios.'),

    # TECH & CARS
    ('Tech & Cars', 'AAPL', 'Apple', 'iPhones, iPads, and MacBooks.'),
    ('Tech & Cars', 'GOOGL', 'Google', 'YouTube, Search, and Android.'),
    ('Tech & Cars', 'TSLA', 'Tesla', 'Electric cars and rockets.'),
    ('Tech & Cars', 'F', 'Ford', 'Mustangs and F-150 Trucks.'),
    ('Tech & Cars', 'TM', 'Toyota', 'Camrys and Priuses.'),
]

# Wipe old list and add new one
cursor.execute('DELETE FROM stock_ideas')
for cat, tick, name, desc in stock_list:
    cursor.execute('INSERT INTO stock_ideas (category, ticker, name, description) VALUES (?, ?, ?, ?)', 
                   (cat, tick, name, desc))

# --- CREATE DEFAULT FAMILY (The Smiths) ---
fam_id = str(uuid.uuid4())
cursor.execute('INSERT INTO families (id, name) VALUES (?, ?)', (fam_id, "The Smith Family"))

# Admin (Dad)
dad_pw = generate_password_hash("password123", method='pbkdf2:sha256')
cursor.execute('INSERT OR IGNORE INTO users (family_id, username, password_hash, is_admin) VALUES (?, ?, ?, ?)', 
              (fam_id, 'Dad', dad_pw, 1))
dad_id = cursor.execute('SELECT id FROM users WHERE username="Dad"').fetchone()[0]
cursor.execute('INSERT OR IGNORE INTO account (user_id, balance) VALUES (?, ?)', (dad_id, 100000.00))

# Kid (Kid1)
kid_pw = generate_password_hash("1234", method='pbkdf2:sha256')
cursor.execute('INSERT OR IGNORE INTO users (family_id, username, password_hash, is_admin) VALUES (?, ?, ?, ?)', 
              (fam_id, 'Kid1', kid_pw, 0))
kid_id = cursor.execute('SELECT id FROM users WHERE username="Kid1"').fetchone()[0]
cursor.execute('INSERT OR IGNORE INTO account (user_id, balance) VALUES (?, ?)', (kid_id, 1000.00))

connection.commit()
connection.close()
print("v6 Database Ready: 35+ Kids Stocks Loaded!")