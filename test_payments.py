import sqlite3

# 1. Function for a MEMBER to report a payment


def member_logs_payment(email, amount, ref_number):
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    # Insert payment with a default status of 'Pending'
    cursor.execute('''
        INSERT INTO payments (user_email, amount, reference_number, status)
        VALUES (?, ?, ?, 'Pending')
    ''', (email, amount, ref_number))

    conn.commit()
    conn.close()
    print(
        f"Success: {email} logged a payment of Ksh {amount}. Status: Pending.")

# 2. Function for the ADMIN to approve the payment


def admin_approves_payment(payment_id):
    conn = sqlite3.connect('sacco.db')
    cursor = conn.cursor()

    # Find the payment details first
    cursor.execute(
        "SELECT user_email, amount, status FROM payments WHERE id = ?", (payment_id,))
    payment = cursor.fetchone()

    if payment and payment[2] == 'Pending':
        user_email = payment[0]
        amount = payment[1]

        # A. Update the payment status to 'Approved'
        cursor.execute(
            "UPDATE payments SET status = 'Approved' WHERE id = ?", (payment_id,))

        # B. Automatically increase the member's balance by that amount!
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE email = ?", (amount, user_email))

        conn.commit()
        print(
            f"Success: Admin approved Payment ID {payment_id}. {user_email}'s balance has been updated!")
    else:
        print("Payment not found or already processed.")

    conn.close()

# --- LET'S RUN THE SIMULATION ---


# Step A: Baba John reports he paid Ksh 2,000 to the bank with a receipt number
print("--- Step A: Member logs a payment ---")
member_logs_payment('baba.john@email.com', 2000.0, 'REF98765')

# Step B: Let's assume this is payment ID 1. The Admin approves it.
print("\n--- Step B: Admin approves the payment ---")
admin_approves_payment(1)
