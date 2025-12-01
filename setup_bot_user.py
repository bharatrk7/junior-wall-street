import sqlite3
import uuid
from werkzeug.security import generate_password_hash

# 1. Connect to Local Database
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print("🤖 Initializing Skynet...")

# 2. Create the Bot Family (if not exists)
fam_id = str(uuid.uuid4())
cursor.execute('INSERT OR IGNORE INTO families (id, name) VALUES (?, ?)', (fam_id, "Skynet"))

# 3. Create the Terminator User
# CRITICAL: Using 'pbkdf2:sha256' to match your Mac's security settings
hashed_pw = generate_password_hash("password123", method='pbkdf2:sha256')

try:
    # Try to insert the bot user
    cursor.execute('''
        INSERT INTO users (family_id, username, password_hash, is_admin) 
        VALUES (?, ?, ?, ?)
    ''', (fam_id, 'The_Terminator', hashed_pw, 0))
    
    user_id = cursor.lastrowid
    
    # 4. Fund the Account ($1,000,000)
    cursor.execute('INSERT INTO account (user_id, balance) VALUES (?, ?)', (user_id, 1000000.00))
    
    conn.commit()
    print("✅ SUCCESS: 'The_Terminator' created with $1,000,000.")

except sqlite3.IntegrityError:
    # If user exists, we UPDATE the password to ensure it's correct
    print("⚠️ User exists. Updating password to be safe...")
    cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', (hashed_pw, 'The_Terminator'))
    conn.commit()
    print("✅ Password repaired.")

conn.close()