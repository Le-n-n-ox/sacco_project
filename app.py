import os
import sqlite3
import re
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail
from flask_mail import Message
from werkzeug.utils import secure_filename
import random
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_sacco_key_replace_this_in_production'

# 📧 EMAIL SERVER CONFIGURATION
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'lexwanys@gmail.com'
app.config['MAIL_PASSWORD'] = 'wjfy bqaz tssp opad'
app.config['MAIL_DEFAULT_SENDER'] = (
    'WealthArc SACCO', 'lexwanys@gmail.com')

mail = Mail(app)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect('sacco.db')
    conn.row_factory = sqlite3.Row
    return conn


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =====================================================================
# 1. CORE GATEWAY ROUTE
# =====================================================================


@app.route('/')
def home_page():
    if 'user_email' not in session:
        return redirect(url_for('login_page'))

    email = session['user_email']
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    total_pool = conn.execute(
        'SELECT SUM(balance) FROM users WHERE role = "member"').fetchone()[0] or 0.0
    total_loans = conn.execute(
        'SELECT SUM(loan_balance) FROM users WHERE role = "member"').fetchone()[0] or 0.0

    # Super Admin Dashboard data aggregation
    pending_admins = []
    if user['role'] == 'super_admin':
        pending_admins = conn.execute(
            'SELECT * FROM users WHERE role = "admin" AND is_approved = 0 ORDER BY email ASC').fetchall()

    conn.close()
    return render_template('home.html', user=user, total_pool=total_pool, total_loans=total_loans, pending_admins=pending_admins)

# =====================================================================
# 2. SEAMLESS AUTHENTICATION & SECURITY HOOKS
# =====================================================================


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password')

        conn = get_db_connection()
        # Find the user by email first
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        # 🔥 SECURE UPGRADE: Check if user exists AND verify the hashed password matches
        if user and check_password_hash(user['password'], password):

            # Check if admin is approved by Super Admin
            if user['is_approved'] == 0:
                return "❌ Access Denied: Your account is pending Super Admin clearance.", 403

            # Log the user into the session safely
            session['user'] = user['email']
            session['role'] = user['role']

            # Route to correct dashboard panel
            if user['role'] == 'super_admin':
                return redirect(url_for('super_admin_dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('member_dashboard'))
        else:
            return "Invalid Credentials! Please try again.", 401

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        dob = request.form.get('dob')
        target_role = request.form.get('role', 'member')

        # Email format validation guard
        # Email format validation guard
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            return "❌ Registration Failed: Please provide a valid email address.", 400

        # 🔄 REPLACE YOUR OLD PASSWORD CHECK WITH THIS ENTIRE COMPLEXITY BLOCK:
        if len(password) < 8:
            return "❌ Registration Failed: Password must be at least 8 characters long.", 400
        if not any(char.isupper() for char in password):
            return "❌ Registration Failed: Password must contain at least one uppercase letter (A-Z).", 400
        if not any(char.isdigit() for char in password):
            return "❌ Registration Failed: Password must contain at least one digit (0-9).", 400
        if not any(not char.isalnum() for char in password):
            return "❌ Registration Failed: Password must contain at least one special character symbol.", 400

        # Check if email is already taken before sending a code
        conn = get_db_connection()
        existing_user = conn.execute(
            'SELECT email FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if existing_user:
            return "❌ Error: An account with that email already exists!", 400

        # 🎲 GENERATE 6-DIGIT VERIFICATION CODE
        verification_code = str(random.randint(100000, 999999))

        # Store form data and code temporarily inside the secure session memory
        session['temp_registration'] = {
            'email': email, 'password': password, 'first_name': first_name,
            'last_name': last_name, 'phone': phone, 'dob': dob, 'role': target_role
        }
        session['verification_code'] = verification_code

        # 📧 SEND THE EMAIL
        try:
            msg = Message("WealthArc SACCO - Verify Your Account Registration",
                          recipients=[email])
            msg.body = f"Hello {first_name},\n\nThank you for signing up with WealthArc SACCO.\nYour 2-Step Verification code is: {verification_code}\n\nPlease enter this code on the verification screen to activate your account."
            mail.send(msg)
        except Exception as e:
            return f"❌ Failed to send verification email. Check server setup. Error: {e}", 500

        # Passcode dispatched! Forward them to the entry validation field pad
        return redirect(url_for('verify_code_page'))

    return render_template('register.html')


@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code_page():
    # If the user somehow loses their session data, kick them back to register safely
    if 'temp_registration' not in session or 'verification_code' not in session:
        return redirect(url_for('register_page'))

    if request.method == 'POST':
        user_input_code = request.form.get('code', '').strip()

        # Check if the code matches what we stored in memory
        # Check if the code matches what we stored in memory
        if user_input_code == session.get('verification_code'):
            reg_data = session['temp_registration']
            approval_status = 0 if reg_data['role'] == 'admin' else 1

            # 🔥 SECURE UPGRADE: Hash the raw password string
            secure_hashed_password = generate_password_hash(
                reg_data['password'])

            conn = get_db_connection()
            try:
                conn.execute("""
                    INSERT INTO users (email, password, role, first_name, last_name, phone, dob, is_approved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (reg_data['email'],
                      secure_hashed_password,  # 👈 Save the encrypted fingerprint instead!
                      reg_data['role'],
                      reg_data['first_name'], reg_data['last_name'], reg_data['phone'], reg_data['dob'], approval_status))
                conn.commit()
            except sqlite3.Error as database_err:
                conn.close()
                return f"❌ Database Save Error: {database_err}", 400
            conn.close()

            # Clean up session memory on SUCCESS
            session.pop('temp_registration', None)
            session.pop('verification_code', None)

            if reg_data['role'] == 'admin':
                return "🎉 Email Verified! Your administrator account is now pending clearance from the Super Admin."

            return redirect(url_for('login_page'))
        else:
            # 💡 FIXED: Instead of crashing on a raw text page, we reload the page
            # and show a clean alert without wiping the session data!
            return render_template('verify.html',
                                   email=session['temp_registration']['email'],
                                   error="❌ Invalid Verification Code! Please double-check your spam or inbox and try again.")

    return render_template('verify.html', email=session['temp_registration']['email'])

# =====================================================================
# 3. SUPER ADMIN COMMAND OVERRIDES
# =====================================================================


@app.route('/approve_admin/<string:email>')
def approve_admin(email):
    if 'user_email' not in session or session.get('user_role') != 'super_admin':
        return "Unauthorized Override!", 403

    conn = get_db_connection()
    conn.execute(
        'UPDATE users SET is_approved = 1 WHERE email = ? AND role = "admin"', (email,))
    conn.commit()
    conn.close()
    return redirect(url_for('home_page'))


@app.route('/deny_admin/<string:email>')
def deny_admin(email):
    if 'user_email' not in session or session.get('user_role') != 'super_admin':
        return "Unauthorized Override!", 403

    conn = get_db_connection()
    # Delete their unverified registration records completely from the cache system
    conn.execute(
        'DELETE FROM users WHERE email = ? AND role = "admin" AND is_approved = 0', (email,))
    conn.commit()
    conn.close()
    return redirect(url_for('home_page'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# =====================================================================
# 4. SUBSIDIARY TERMINALS (MEMBER & ADMIN)
# =====================================================================


@app.route('/dashboard')
def member_dashboard():
    if 'user_email' not in session:
        return redirect(url_for('login_page'))
    email = session['user_email']
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    payments = conn.execute(
        'SELECT * FROM payments WHERE user_email = ? ORDER BY id DESC', (email,)).fetchall()
    total_pool = conn.execute(
        'SELECT SUM(balance) FROM users WHERE role = "member"').fetchone()[0] or 0.0
    total_loans = conn.execute(
        'SELECT SUM(loan_balance) FROM users WHERE role = "member"').fetchone()[0] or 0.0
    community_members = conn.execute(
        'SELECT first_name, last_name, balance, loan_balance, profile_pic FROM users WHERE role = "member" ORDER BY balance DESC').fetchall()
    conn.close()
    return render_template('member.html', user=user, payments=payments, total_pool=total_pool, total_loans=total_loans, community=community_members)


@app.route('/submit_payment', methods=['POST'])
def submit_payment():
    if 'user_email' not in session:
        return redirect(url_for('login_page'))
    email = session['user_email']
    amount = float(request.form.get('amount', 0))
    ref_num = request.form.get('reference_number', '').upper()
    conn = get_db_connection()
    conn.execute('INSERT INTO payments (user_email, amount, reference_number) VALUES (?, ?, ?)',
                 (email, amount, ref_num))
    conn.commit()
    conn.close()
    return redirect(url_for('member_dashboard'))


@app.route('/admin')
def admin_dashboard():
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return redirect(url_for('login_page'))
    conn = get_db_connection()
    pending_payments = conn.execute(
        'SELECT * FROM payments WHERE status = "Pending" ORDER BY id DESC').fetchall()
    members_list = conn.execute(
        'SELECT email, balance, loan_balance, first_name, last_name, phone, dob, profile_pic FROM users WHERE role = "member" ORDER BY email ASC').fetchall()
    payment_history = conn.execute(
        'SELECT * FROM payments ORDER BY date_submitted DESC').fetchall()
    total_pool = conn.execute(
        'SELECT SUM(balance) FROM users WHERE role = "member"').fetchone()[0] or 0.0
    total_loans = conn.execute(
        'SELECT SUM(loan_balance) FROM users WHERE role = "member"').fetchone()[0] or 0.0
    conn.close()
    return render_template('admin.html', pending=pending_payments, members=members_list, history=payment_history, total_pool=total_pool, total_loans=total_loans)


@app.route('/update_loan', methods=['POST'])
def update_loan():
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return "Unauthorized Access!", 403
    member_email = request.form.get('member_email')
    new_loan_amount = float(request.form.get('loan_amount', 0.0))
    conn = get_db_connection()
    conn.execute('UPDATE users SET loan_balance = ? WHERE email = ?',
                 (new_loan_amount, member_email))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/approve/<int:payment_id>')
def approve_payment(payment_id):
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return redirect(url_for('login_page'))
    conn = get_db_connection()
    payment = conn.execute(
        'SELECT * FROM payments WHERE id = ?', (payment_id,)).fetchone()
    if payment and payment['status'] == 'Pending':
        conn.execute(
            'UPDATE payments SET status = "Approved" WHERE id = ?', (payment_id,))
        conn.execute('UPDATE users SET balance = balance + ? WHERE email = ?',
                     (payment['amount'], payment['user_email']))
        conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/reject/<int:payment_id>')
def reject_payment(payment_id):
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return redirect(url_for('login_page'))
    conn = get_db_connection()
    conn.execute(
        'UPDATE payments SET status = "Rejected" WHERE id = ?', (payment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/delete_member/<string:email>')
def delete_member(email):
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return redirect(url_for('login_page'))
    conn = get_db_connection()
    conn.execute(
        'DELETE FROM users WHERE email = ? AND role = "member"', (email,))
    conn.execute('DELETE FROM payments WHERE user_email = ?', (email,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
