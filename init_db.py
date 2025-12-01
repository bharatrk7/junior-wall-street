import sqlite3
import os
import uuid
import psycopg2
from werkzeug.security import generate_password_hash

# --- CONFIGURATION ---
IS_CLOUD = 'DATABASE_URL' in os.environ

def get_db():
    if IS_CLOUD:
        return psycopg2.connect(os.environ['DATABASE_URL'])
    else:
        return sqlite3.connect('trading.db')

def get_ph():
    """Returns the correct placeholder: %s for Postgres, ? for SQLite"""
    return '%s' if IS_CLOUD else '?'

# --- CONNECT ---
connection = get_db()
cursor = connection.cursor()
ph = get_ph()

print(f"🔧 Initializing Database ({'Postgres' if IS_CLOUD else 'SQLite'})...")

# --- DROP TABLES (Clean Slate) ---
# We drop tables to ensure a clean setup on every run
tables = ['stock_ideas', 'transactions', 'portfolio', 'account', 'users', 'families']
for table in tables:
    cursor.execute(f'DROP TABLE IF EXISTS {table} CASCADE' if IS_CLOUD else f'DROP TABLE IF EXISTS {table}')

# --- CREATE TABLES ---

# 1. FAMILIES
cursor.execute(f'''
    CREATE TABLE families (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
''')

# 2. USERS
cursor.execute(f'''
    CREATE TABLE users (
        id {'SERIAL' if IS_CLOUD else 'INTEGER'} PRIMARY KEY,
        family_id TEXT NOT NULL,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin {'BOOLEAN' if IS_CLOUD else 'INTEGER'} DEFAULT 0,
        FOREIGN KEY (family_id) REFERENCES families (id),
        UNIQUE(family_id, username)
    )
''')

# 3. ACCOUNT
cursor.execute(f'''
    CREATE TABLE account (
        id {'SERIAL' if IS_CLOUD else 'INTEGER'} PRIMARY KEY,
        user_id INTEGER NOT NULL,
        balance REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

# 4. PORTFOLIO
cursor.execute(f'''
    CREATE TABLE portfolio (
        id {'SERIAL' if IS_CLOUD else 'INTEGER'} PRIMARY KEY,
        user_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        shares INTEGER NOT NULL,
        avg_price REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

# 5. TRANSACTIONS
cursor.execute(f'''
    CREATE TABLE transactions (
        id {'SERIAL' if IS_CLOUD else 'INTEGER'} PRIMARY KEY,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        ticker TEXT NOT NULL,
        shares INTEGER NOT NULL,
        price REAL NOT NULL,
        timestamp {'TIMESTAMP' if IS_CLOUD else 'DATETIME'} DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')

# 6. STOCK IDEAS
cursor.execute(f'''
    CREATE TABLE stock_ideas (
        id {'SERIAL' if IS_CLOUD else 'INTEGER'} PRIMARY KEY,
        category TEXT NOT NULL,
        ticker TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT
    )
''')

# --- SEED DATA ---

# Stocks
stock_list = [
    ('Video Games', 'RBLX', 'Roblox', 'The platform where you build and play games.'),
    ('Video Games', 'NTDOY', 'Nintendo', 'Mario, Zelda, Pokemon, and the Switch.'),
    ('Video Games', 'EA', 'Electronic Arts', 'FIFA, Madden, and The Sims.'),
    ('Video Games', 'MSFT', 'Microsoft (Xbox)', 'Xbox, Minecraft, and Windows computers.'),
    ('Social Media', 'SNAP', 'Snapchat', 'Filters, streaks, and messaging.'),
    ('Snacks & Food', 'MCD', 'McDonalds', 'Big Macs, Fries, and Happy Meals.'),
    ('Snacks & Food', 'KO', 'Coca-Cola', 'Coke, Sprite, and Dasani Water.'),
    ('Toys', 'MAT', 'Mattel', 'Barbie and Hot Wheels.'),
    ('Toys', 'HAS', 'Hasbro', 'Nerf, Monopoly, and Transformers.'),
    ('Tech', 'AAPL', 'Apple', 'iPhones, iPads, and MacBooks.'),
    ('Tech', 'GOOGL', 'Google', 'YouTube, Search, and Android.'),
    ('Tech', 'NFLX', 'Netflix', 'Streaming movies and Stranger Things.'),
    ('Cars', 'TSLA', 'Tesla', 'Electric cars.'),
    ('Clothes', 'NKE', 'Nike', 'Air Jordans, sneakers, and sports gear.'),
    ('Entertainment', 'DIS', 'Disney', 'Marvel, Star Wars, Pixar, and Theme Parks.')
]

for cat, tick, name, desc in stock_list:
    cursor.execute(f'INSERT INTO stock_ideas (category, ticker, name, description) VALUES ({ph}, {ph}, {ph}, {ph})', 
                   (cat, tick, name, desc))

# Default Family (The Smiths)
fam_id = str(uuid.uuid4())
cursor.execute(f'INSERT INTO families (id, name) VALUES ({ph}, {ph})', (fam_id, "The Smiths"))

# Users
dad_pw = generate_password_hash("password123", method='pbkdf2:sha256')
kid_pw = generate_password_hash("1234", method='pbkdf2:sha256')

# Helper to get ID
def get_new_id(cursor):
    return cursor.fetchone()[0] if IS_CLOUD else cursor.lastrowid

# Create Dad
if IS_CLOUD:
    cursor.execute(f'INSERT INTO users (family_id, username, password_hash, is_admin) VALUES ({ph}, {ph}, {ph}, {ph}) RETURNING id', 
                  (fam_id, 'Dad', dad_pw, 1))
    dad_id = cursor.fetchone()[0]
else:
    cursor.execute(f'INSERT INTO users (family_id, username, password_hash, is_admin) VALUES ({ph}, {ph}, {ph}, {ph})', 
                  (fam_id, 'Dad', dad_pw, 1))
    dad_id = cursor.lastrowid

cursor.execute(f'INSERT INTO account (user_id, balance) VALUES ({ph}, {ph})', (dad_id, 100000.00))

# Create Kid
if IS_CLOUD:
    cursor.execute(f'INSERT INTO users (family_id, username, password_hash, is_admin) VALUES ({ph}, {ph}, {ph}, {ph}) RETURNING id', 
                  (fam_id, 'Kid1', kid_pw, 0))
    kid_id = cursor.fetchone()[0]
else:
    cursor.execute(f'INSERT INTO users (family_id, username, password_hash, is_admin) VALUES ({ph}, {ph}, {ph}, {ph})', 
                  (fam_id, 'Kid1', kid_pw, 0))
    kid_id = cursor.lastrowid

cursor.execute(f'INSERT INTO account (user_id, balance) VALUES ({ph}, {ph})', (kid_id, 1000.00))

connection.commit()
connection.close()
print("✅ Database Seeded Successfully!")