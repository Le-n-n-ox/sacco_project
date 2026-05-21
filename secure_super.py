import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('sacco.db')
cursor = conn.cursor()

# Generate a secure hash for the super admin password
hashed_pass = generate_password_hash('super123')

# Update the database record
cursor.execute(
    "UPDATE users SET password = ? WHERE email = 'super@sacco.com';", (hashed_pass,))
conn.commit()
conn.close()

print("🔐 Super Admin account upgraded to secure cryptographic hashing successfully!")
