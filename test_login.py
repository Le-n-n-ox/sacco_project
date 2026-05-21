import sqlite3


def simulate_login(email, password):
    # 1. Connect to the database
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    # 2. Look for a user with this exact email and password
    cursor.execute(
        "SELECT role, balance FROM users WHERE email = ? AND password = ?", (email, password))
    user = cursor.fetchone()

    conn.close()

    # 3. Check the result
    if user:
        role = user[0]
        balance = user[1]
        if role == 'admin':
            return "Success! Logged in as ADMIN. You can monitor all finances."
        else:
            return f"Success! Logged in as MEMBER. Your current balance is: Ksh {balance}"
    else:
        return "Login Failed! Wrong email or password."


# --- TEST THE SIMULATOR ---
# Let's try to log in with the member email we created earlier
print("Trying member login...")
result = simulate_login('member@sacco.com', 'member123')
print(result)

print("\nTrying a wrong password...")
wrong_result = simulate_login('member@sacco.com', 'wrong_password')
print(wrong_result)
