import sqlite3

conn = sqlite3.connect('sacco.db')
cursor = conn.cursor()

# 1. Clear out any broken or conflicting old super admin rows
cursor.execute("DELETE FROM users WHERE email = 'super@sacco.com';")

# 2. Insert a fresh, clean, fully approved Super Admin account
try:
    cursor.execute("""
    INSERT INTO users (
        email, password, role, balance, loan_balance, 
        first_name, last_name, phone, dob, profile_pic, is_approved
    ) VALUES (
        'super@sacco.com', 'super123', 'super_admin', 0.0, 0.0, 
        'Chief', 'Executive', '111222333', '1990-01-01', 'default.png', 1
    );
    """)
    conn.commit()
    print("✨ SUCCESS: Super Admin account has been cleanly reconstructed!")
    print("👉 Username ID: super@sacco.com")
    print("👉 Password: super123")
except sqlite3.Error as e:
    print(f"❌ Database Error: {e}")

conn.close()
