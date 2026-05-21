import sqlite3


def setup_loan_columns():
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    # Add loan field to users table if it doesn't exist
    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN loan_balance REAL DEFAULT 0.0;")
        print("✅ Added 'loan_balance' column to users table!")
    except sqlite3.OperationalError:
        print("ℹ️ 'loan_balance' column already exists.")

    conn.commit()
    conn.close()
    print("🚀 Database modified successfully for loans!")


if __name__ == '__main__':
    setup_loan_columns()
