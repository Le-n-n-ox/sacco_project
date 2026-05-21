import sqlite3


def init_database():
    # Connect to the database file (creates it if it doesn't exist)
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    print("⏳ Building SACCO database architecture...")

    # 1. Create the updated users table with profile fields & loan tracking
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
        profile_pic TEXT DEFAULT 'default.png'
    );
    """)

    # 2. Create the payments tracking table for member deposits
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

    # 3. Pre-seed the default Master Administrator account
    try:
        cursor.execute("""
        INSERT INTO users (email, password, role, balance, loan_balance, first_name, last_name, phone, dob, profile_pic)
        VALUES ('admin@sacco.com', 'admin123', 'admin', 0.0, 0.0, 'System', 'Administrator', '0000000000', '2000-01-01', 'default.png')
        """)
        print("✅ Master Admin account seeded: (admin@sacco.com / admin123)")
    except sqlite3.IntegrityError:
        # Avoids crashing if the admin account is already present
        print("ℹ️ Master Admin account already exists, skipping seed.")

    # Commit changes and shut down the connection cleanly
    conn.commit()
    conn.close()
    print("🚀 Database initialized with all modern columns successfully!")


if __name__ == '__main__':
    init_database()
