import sqlite3


def add_new_member(email, password, starting_balance):
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    try:
        # Insert the new member into the users table
        cursor.execute(
            "INSERT INTO users (email, password, role, balance) VALUES (?, ?, 'member', ?)",
            (email, password, starting_balance)
        )
        conn.commit()
        print(f"Success! Member {email} has been added.")
    except sqlite3.IntegrityError:
        # This triggers if you try to add an email that already exists
        print(f"Error: A user with the email {email} already exists!")

    conn.close()


# --- Let's add a couple of real members to test it ---
print("Adding members...")
add_new_member('grandma.mariah@email.com', 'mama2026', 2500.0)
add_new_member('baba.john@email.com', 'baba1234', 5000.0)
