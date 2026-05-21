import sqlite3

def init_db():
    # Connect to SQLite database (it will create the file if it doesn't exist)
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    # 1. Create the Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'member', -- Can be 'member' or 'admin'
            balance REAL DEFAULT 0.0
        )
    ''')

    # 2. Create the Payments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            amount REAL NOT NULL,
            reference_number TEXT NOT NULL,
            status TEXT DEFAULT 'Pending', -- Can be 'Pending', 'Approved', or 'Rejected'
            date_submitted DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users (email)
        )
    ''')

    # Insert a sample Admin and Member just so we have data to test with later
    try:
        # Default Admin login: admin@sacco.com / password: admin123
        cursor.execute("INSERT INTO users (email, password, role) VALUES (?, ?, ?)", 
                       ('admin@sacco.com', 'admin123', 'admin'))
        
        # Default Member login: member@sacco.com / password: member123
        cursor.execute("INSERT INTO users (email, password, role, balance) VALUES (?, ?, ?, ?)", 
                       ('member@sacco.com', 'member123', 'member', 1500.00))
        
        conn.commit()
        print("Database initialized successfully with sample users!")
    except sqlite3.IntegrityError:
        # This prevents errors if you run the script more than once
        print("Database already exists and is ready.")
        
    conn.close()

if __name__ == '__main__':
    init_db()