import sqlite3


def upgrade_database():
    print("🔄 Connecting to sacco.db...")
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    # 1. Create the loan_requests table
    print("📝 Creating loan_requests table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loan_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            amount REAL NOT NULL,
            period_months INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            date_applied TEXT NOT NULL
        )
    ''')

    # 2. Create the active_loans table
    print("🏦 Creating active_loans table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            principal_amount REAL NOT NULL,
            interest_rate REAL NOT NULL,
            monthly_payment REAL NOT NULL,
            maturity_date TEXT NOT NULL,
            status TEXT DEFAULT 'Active'
        )
    ''')

    # 3. Create the repayment_schedules table
    print("📅 Creating repayment_schedules table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS repayment_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            amount REAL NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    ''')

    # Save changes and close
    conn.commit()
    conn.close()
    print("✅ Database migration complete! Your SACCO system is ready for the new loan features.")


if __name__ == '__main__':
    upgrade_database()
