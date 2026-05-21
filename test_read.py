import sqlite3

# 1. Connect to the database file we made
conn = sqlite3.connect('sacco.db')
cursor = conn.cursor()

# 2. Ask it to grab the email and role of everyone inside
cursor.execute("SELECT email, role FROM users")
all_users = cursor.fetchall()

# 3. Print the results to your screen
print("Users in database:", all_users)

conn.close()
