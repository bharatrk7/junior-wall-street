import sqlite3

# Connect to the local file
try:
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    print("\n🔍 INSPECTING DATABASE USERS...")
    print("-" * 40)
    
    try:
        users = cursor.execute('SELECT id, username, is_admin, family_id FROM users').fetchall()
        
        if not users:
            print("❌ The database is EMPTY. No users found.")
            print("👉 Fix: Run 'python init_db.py' immediately.")
        else:
            for u in users:
                # 0=ID, 1=Username, 2=Admin, 3=FamilyID
                admin_status = "Admin (Dad)" if u[2] else "User"
                print(f"✅ User: '{u[1]}' | Role: {admin_status} | ID: {u[0]}")
                
    except sqlite3.OperationalError:
        print("❌ ERROR: The 'users' table does not exist.")
        print("👉 Fix: Run 'python init_db.py' to build the tables.")

    conn.close()

except Exception as e:
    print(f"❌ Could not connect to database: {e}")