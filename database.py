import sqlite3
from werkzeug.security import generate_password_hash


def init_database():
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    print("⏳ Building SACCO database architecture...")

    # 1. Core Users Ledger Structure
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        balance REAL DEFAULT 0.0,
        loan_balance REAL DEFAULT 0.0,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        dob TEXT,
        profile_pic TEXT DEFAULT 'default.png',
        is_approved INTEGER DEFAULT 0
    );
    """)

    # 2. Financial Payments Flow Engine
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        amount REAL NOT NULL,
        reference_number TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        date_submitted TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Dynamic Application Settings Registry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # Pre-seed Calculator Parameters
    cursor.execute(
        'INSERT OR IGNORE INTO settings (key, value) VALUES ("interest_rate", "0.01")')

    # 4. Generate Core Secure Cryptographic Hashes
    hashed_admin_pass = generate_password_hash('admin123')
    hashed_super_pass = generate_password_hash('super123')

    # Seed Master Standard Admin Account
    try:
        cursor.execute("""
        INSERT INTO users (email, password, role, balance, loan_balance, first_name, last_name, phone, dob, profile_pic, is_approved)
        VALUES ('admin@sacco.com', ?, 'admin', 0.0, 0.0, 'System', 'Admin', '0000000000', '2000-01-01', 'default.png', 1)
        """, (hashed_admin_pass,))
        print("✅ Master Admin account seeded: (admin@sacco.com / admin123)")
    except sqlite3.IntegrityError:
        print("ℹ️ Master Admin account already exists, skipping seed.")

    # Seed Higher Sovereign Super Admin Account
    try:
        cursor.execute("""
        INSERT INTO users (email, password, role, balance, loan_balance, first_name, last_name, phone, dob, profile_pic, is_approved)
        VALUES ('super@sacco.com', ?, 'super_admin', 0.0, 0.0, 'Super', 'Admin', '1112223333', '1995-01-01', 'default.png', 1)
        """, (hashed_super_pass,))
        print("👑 Super Admin master node seeded successfully: (super@sacco.com / super123)")
    except sqlite3.IntegrityError:
        print("ℹ️ Super Admin account already exists, skipping seed.")

    conn.commit()
    conn.close()
    print("🚀 Database initialized with all modern tables and records successfully!")


if __name__ == '__main__':
    init_database()
