import sqlite3


def init_db():
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    # Create Users table with ALL columns used in your app.py
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            balance REAL DEFAULT 0.0,
            loan_balance REAL DEFAULT 0.0,
            first_name TEXT DEFAULT 'Member',
            last_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            dob TEXT DEFAULT '',
            is_approved INTEGER DEFAULT 0,
            profile_pic TEXT DEFAULT 'default.png'
        )
    ''')

    # Payments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            amount REAL NOT NULL,
            reference_number TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            date_submitted DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users (email)
        )
    ''')

    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value REAL NOT NULL
        )
    ''')

    # Set default interest rate
    cursor.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('interest_rate', 0.01)")

    conn.commit()
    conn.close()
    print("Database initialized successfully with all columns.")


if __name__ == '__main__':
    init_db()
