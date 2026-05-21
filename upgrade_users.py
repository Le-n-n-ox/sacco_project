import sqlite3

conn = sqlite3.connect('sacco.db')
cursor = conn.cursor()

try:
    # 1. Add approval flag column (Defaults to 1 so existing members/admins aren't accidentally locked out)
    cursor.execute(
        "ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 1;")
    conn.commit()
    print("✅ Successfully injected 'is_approved' column flag.")
except sqlite3.OperationalError:
    print("ℹ️ Column 'is_approved' already exists, skipping.")

conn.close()
