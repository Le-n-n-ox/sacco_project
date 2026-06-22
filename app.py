import os
import psycopg2
from psycopg2.extras import DictCursor
import re
import random
import flask
from flask import g
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import requests
from requests.auth import HTTPBasicAuth
import base64

app = flask.Flask(__name__)
app.secret_key = 'super_secret_sacco_key_replace_this_in_production'

# 📧 EMAIL SERVER CONFIGURATION
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'lexwanys@gmail.com'
app.config['MAIL_PASSWORD'] = 'wjfy bqaz tssp opad'
app.config['MAIL_DEFAULT_SENDER'] = ('WealthArc SACCO', 'lexwanys@gmail.com')

mail = Mail(app)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def get_db_connection():
    """Opens a safe, isolated database connection attached to the current request context targeting PostgreSQL."""
    if 'db' not in g:
        g.db = psycopg2.connect(
            host="localhost",
            database="sacco_project",
            user="postgres",
            # ⚠️ Replace this with your exact pgAdmin installation password
            password="1111",
            port="5432"
        )
    return g.db


@app.teardown_appcontext
def close_db_connection(exception=None):
    """Fail-safe hook that automatically closes connections, even if a route crashes."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =====================================================================
# 1. CORE GATEWAY ROUTE
# =====================================================================


@app.route('/')
def home_page():
    if 'user' not in flask.session and 'user_email' not in flask.session:
        return flask.redirect(flask.url_for('login_page'))

    current_user_email = flask.session.get(
        'user') or flask.session.get('user_email')

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute('SELECT * FROM users WHERE email = %s', (current_user_email,))
    user = cur.fetchone()
    cur.close()

    if user is None:
        flask.session.clear()
        return flask.redirect(flask.url_for('login_page'))

    if user['role'] == 'super_admin':
        return flask.redirect(flask.url_for('super_admin_dashboard'))
    elif user['role'] == 'admin':
        return flask.redirect(flask.url_for('admin_dashboard'))
    else:
        return flask.redirect(flask.url_for('member_dashboard'))

# =====================================================================
# 2. SEAMLESS AUTHENTICATION & SECURITY HOOKS
# =====================================================================


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if flask.request.method == 'POST':
        email = flask.request.form.get('email', '').strip()
        password = flask.request.form.get('password', '')

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        cur.close()

        # 🔍 TERMINAL DIAGNOSTICS
        print("\n=== SACCO GATEWAY VALIDATION ===")
        print(f"Target Email Entered: {email}")
        print(f"User Record Located?: {'YES' if user else 'NO'}")
        if user:
            print(f"Assigned DB Role   : {user['role']}")
            print(
                f"Cryptographic Match : {check_password_hash(user['password'], password)}")
        print("=================================\n")

        if user and check_password_hash(user['password'], password):
            # Block unapproved standard administrators
            if user['role'] == 'admin' and int(user['is_approved'] or 0) != 1:
                return "Account pending approval from Super Admin.", 403

            # 🔐 UNIFIED SESSION ARRAYS
            flask.session['user'] = user['email']
            flask.session['user_email'] = user['email']
            flask.session['role'] = user['role']
            flask.session['user_role'] = user['role']
            return flask.redirect(flask.url_for('home_page'))

        return flask.redirect(flask.url_for('login_page'))

    return flask.render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if flask.request.method == 'POST':
        email = flask.request.form.get('email', '').strip()
        password = flask.request.form.get('password', '')
        first_name = flask.request.form.get('first_name', '').strip()
        last_name = flask.request.form.get('last_name', '').strip()
        phone = flask.request.form.get('phone', '').strip()
        dob = flask.request.form.get('dob', '')
        target_role = flask.request.form.get('role', 'member')

        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            return "❌ Registration Failed: Please provide a valid email address.", 400

        if len(password) < 8:
            return "❌ Registration Failed: Password must be at least 8 characters long.", 400
        if not any(char.isupper() for char in password):
            return "❌ Registration Failed: Password must contain at least one uppercase letter (A-Z).", 400
        if not any(char.isdigit() for char in password):
            return "❌ Registration Failed: Password must contain at least one digit (0-9).", 400
        if not any(not char.isalnum() for char in password):
            return "❌ Registration Failed: Password must contain at least one special character symbol.", 400

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute('SELECT email FROM users WHERE email = %s', (email,))
        existing_user = cur.fetchone()
        cur.close()

        if existing_user:
            return "❌ Error: An account with that email already exists!", 400

        verification_code = str(random.randint(100000, 999999))

        flask.session['temp_registration'] = {
            'email': email, 'password': password, 'first_name': first_name,
            'last_name': last_name, 'phone': phone, 'dob': dob, 'role': target_role
        }
        flask.session['verification_code'] = verification_code

        try:
            msg = Message(
                "WealthArc SACCO - Verify Your Account Registration", recipients=[email])
            msg.body = f"Hello {first_name},\n\nThank you for signing up with WealthArc SACCO.\nYour 2-Step Verification code is: {verification_code}\n\nPlease enter this code on the verification screen to activate your account."
            mail.send(msg)
        except Exception as e:
            return f"❌ Failed to send verification email. Error: {e}", 500

        return flask.redirect(flask.url_for('verify_code_page'))

    return flask.render_template('register.html')


@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code_page():
    if 'temp_registration' not in flask.session or 'verification_code' not in flask.session:
        return flask.redirect(flask.url_for('register_page'))

    if flask.request.method == 'POST':
        user_input_code = flask.request.form.get('code', '').strip()

        if user_input_code == flask.session.get('verification_code'):
            reg_data = flask.session['temp_registration']
            approval_status = 0 if reg_data['role'] == 'admin' else 1

            secure_hashed_password = generate_password_hash(
                reg_data['password'])

            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO users (email, password, role, first_name, last_name, phone, dob, is_approved)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (reg_data['email'], secure_hashed_password, reg_data['role'],
                      reg_data['first_name'], reg_data['last_name'], reg_data['phone'], reg_data['dob'], approval_status))
                conn.commit()
            except psycopg2.Error as database_err:
                cur.close()
                return f"❌ Database Save Error: {database_err}", 400
            cur.close()

            flask.session.pop('temp_registration', None)
            flask.session.pop('verification_code', None)

            if reg_data['role'] == 'admin':
                return "🎉 Email Verified! Your administrator account is now pending clearance from the Super Admin."

            return flask.redirect(flask.url_for('login_page'))
        else:
            return flask.render_template('verify.html',
                                         email=flask.session['temp_registration']['email'],
                                         error="❌ Invalid Verification Code! Please try again.")

    return flask.render_template('verify.html', email=flask.session['temp_registration']['email'])

# =====================================================================
# 3. SUPER ADMIN COMMAND OVERRIDES
# =====================================================================


@app.route('/approve_admin/<string:email>')
def approve_admin(email):
    if 'user_email' not in flask.session or flask.session.get('user_role') != 'super_admin':
        return "Unauthorized Override!", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_approved = 1 WHERE email = %s AND role = 'admin'", (email,))
    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('home_page'))


@app.route('/deny_admin/<string:email>')
def deny_admin(email):
    if 'user_email' not in flask.session or flask.session.get('user_role') != 'super_admin':
        return "Unauthorized Override!", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM users WHERE email = %s AND role = 'admin' AND is_approved = 0", (email,))
    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('home_page'))


@app.route('/logout')
def logout():
    flask.session.clear()
    return flask.redirect(flask.url_for('login_page'))

# =====================================================================
# 4. SUBSIDIARY TERMINALS (MEMBER & ADMIN)
# =====================================================================


@app.route('/dashboard')
def member_dashboard():
    if 'user_email' not in flask.session:
        return flask.redirect(flask.url_for('login_page'))

    email = flask.session['user_email']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("SELECT value FROM settings WHERE key = 'interest_rate'")
    rate_row = cur.fetchone()
    interest_rate = float(rate_row['value']) if rate_row else 0.01

    cur.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = cur.fetchone()

    cur.execute(
        'SELECT * FROM payments WHERE user_email = %s ORDER BY id DESC', (email,))
    payments = cur.fetchall()

    cur.execute(
        'SELECT SUM(balance) AS total FROM users WHERE role = \'member\'')
    total_pool_row = cur.fetchone()
    total_pool = float(
        total_pool_row['total']) if total_pool_row and total_pool_row['total'] is not None else 0.0

    cur.execute(
        'SELECT SUM(loan_balance) AS total FROM users WHERE role = \'member\'')
    total_loans_row = cur.fetchone()
    total_loans = float(
        total_loans_row['total']) if total_loans_row and total_loans_row['total'] is not None else 0.0

    cur.execute('SELECT first_name, last_name, balance, loan_balance, profile_pic FROM users WHERE role = \'member\' ORDER BY balance DESC')
    community_members = cur.fetchall()

    # --- LOAN DATA FETCHING ---
    try:
        cur.execute(
            'SELECT * FROM loan_requests WHERE user_email = %s ORDER BY id DESC', (email,))
        loan_requests = cur.fetchall()

        cur.execute(
            "SELECT * FROM active_loans WHERE user_email = %s AND status = 'Active' ORDER BY id DESC LIMIT 1", (email,))
        active_loan_query = cur.fetchone()

        cur.execute(
            'SELECT * FROM repayment_schedules WHERE user_email = %s ORDER BY due_date ASC', (email,))
        repayment_schedule = cur.fetchall()
    except psycopg2.Error:
        # Fallback tracking safely catches anomalies if table layouts are out of alignment
        loan_requests = []
        active_loan_query = None
        repayment_schedule = []

    # Format active loan data for the template UI
    active_loan = {}
    if active_loan_query:
        active_loan = {
            'interest_rate': active_loan_query['interest_rate'],
            'monthly_payment': active_loan_query['monthly_payment'],
            'maturity_date': active_loan_query['maturity_date']
        }
    elif user['loan_balance'] and user['loan_balance'] > 0:
        active_loan = {
            'interest_rate': interest_rate * 100,
            'monthly_payment': 'Pending Sync',
            'maturity_date': 'Pending Sync'
        }

    cur.close()
    return flask.render_template('member.html',
                                 user=user,
                                 payments=payments,
                                 total_pool=total_pool,
                                 total_loans=total_loans,
                                 community=community_members,
                                 interest_rate=interest_rate,
                                 loan_requests=loan_requests,
                                 active_loan=active_loan,
                                 repayment_schedule=repayment_schedule)


@app.route('/apply_loan', methods=['POST'])
def apply_loan():
    if 'user_email' not in flask.session:
        return flask.redirect(flask.url_for('login_page'))

    email = flask.session['user_email']

    raw_amount = flask.request.form.get('loan_amount', '0').strip()
    amount = float(raw_amount) if raw_amount else 0.0

    raw_period = flask.request.form.get('loan_period', '12').strip()
    period = int(raw_period) if raw_period else 12

    purpose = flask.request.form.get('loan_purpose', '').strip()
    date_applied = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO loan_requests (user_email, amount, period_months, purpose, status, date_applied)
            VALUES (%s, %s, %s, %s, 'Pending', %s)
        ''', (email, amount, period, purpose, date_applied))
        conn.commit()
    except psycopg2.Error as e:
        print(f"⚠️ Warning: Please create the loan_requests table! Error: {e}")
    finally:
        cur.close()

    return flask.redirect(flask.url_for('member_dashboard'))


@app.route('/submit_payment', methods=['POST'])
def submit_payment():
    if 'user_email' not in flask.session:
        return flask.redirect(flask.url_for('login_page'))
    email = flask.session['user_email']

    raw_amount = flask.request.form.get('amount', '0').strip()
    amount = float(raw_amount) if raw_amount else 0.0

    ref_num = flask.request.form.get('reference_number', '').upper().strip()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO payments (user_email, amount, reference_number) VALUES (%s, %s, %s)',
                (email, amount, ref_num))
    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('member_dashboard'))


@app.route('/admin')
def admin_dashboard():
    current_role = flask.session.get('role') or flask.session.get('user_role')
    if ('user' not in flask.session and 'user_email' not in flask.session) or current_role != 'admin':
        return flask.redirect(flask.url_for('login_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("SELECT * FROM users WHERE role = 'member'")
    users = cur.fetchall()

    cur.execute("""
        SELECT * FROM payments 
        WHERE LOWER(status) = 'pending' OR status IS NULL
    """)
    pending_payments = cur.fetchall()

    cur.execute("SELECT * FROM payments ORDER BY id DESC")
    ledger_history = cur.fetchall()

    cur.execute(
        'SELECT SUM(balance) AS total FROM users WHERE role = \'member\'')
    pool_sum_row = cur.fetchone()
    pool_sum = float(
        pool_sum_row['total']) if pool_sum_row and pool_sum_row['total'] is not None else 0.0

    cur.execute(
        "SELECT * FROM loan_requests WHERE status = 'Pending' ORDER BY id DESC")
    pending_loans = cur.fetchall()

    cur.execute('SELECT value FROM settings WHERE key = \'interest_rate\'')
    rate_row = cur.fetchone()
    current_rate_percent = float(rate_row['value']) * 100 if rate_row else 1.0

    cur.close()

    return flask.render_template('admin.html',
                                 members=users,
                                 pending=pending_payments,
                                 history=ledger_history,
                                 total_pool=pool_sum,
                                 pending_loans=pending_loans,
                                 current_rate=current_rate_percent)


@app.route('/update_loan', methods=['POST'])
def update_loan():
    if 'user_email' not in flask.session or flask.session.get('user_role') != 'admin':
        return "Unauthorized Access!", 403
    member_email = flask.request.form.get('member_email')

    raw_loan_amount = flask.request.form.get('loan_amount', '0').strip()
    new_loan_amount = float(raw_loan_amount) if raw_loan_amount else 0.0

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE users SET loan_balance = %s WHERE email = %s',
                (new_loan_amount, member_email))
    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('admin_dashboard'))


@app.route('/approve/<int:payment_id>')
def approve_payment(payment_id):
    if 'user_email' not in flask.session or flask.session.get('user_role') != 'admin':
        return flask.redirect(flask.url_for('login_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute('SELECT * FROM payments WHERE id = %s', (payment_id,))
    payment = cur.fetchone()

    if payment and (payment['status'] is None or payment['status'].lower() == 'pending'):
        cur.execute(
            'UPDATE payments SET status = \'Approved\' WHERE id = %s', (payment_id,))
        cur.execute('UPDATE users SET balance = balance + %s WHERE email = %s',
                    (payment['amount'], payment['user_email']))
        conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('admin_dashboard'))


@app.route('/reject/<int:payment_id>')
def reject_payment(payment_id):
    if 'user_email' not in flask.session or flask.session.get('user_role') != 'admin':
        return flask.redirect(flask.url_for('login_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'UPDATE payments SET status = \'Rejected\' WHERE id = %s', (payment_id,))
    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('admin_dashboard'))


@app.route('/delete_member/<string:email>')
def delete_member(email):
    if 'user_email' not in flask.session or flask.session.get('user_role') != 'admin':
        return flask.redirect(flask.url_for('login_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM users WHERE email = %s AND role = 'member'", (email,))
    cur.execute('DELETE FROM payments WHERE user_email = %s', (email,))
    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('admin_dashboard'))


@app.route('/calculator')
def loan_calculator():
    return flask.render_template('calculator.html')


@app.route('/super-admin-dashboard')
def super_admin_dashboard():
    if 'user' not in flask.session or flask.session.get('role') != 'super_admin':
        return flask.redirect(flask.url_for('login_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("""
        SELECT email, first_name, last_name, phone, dob 
        FROM users 
        WHERE role = 'admin' AND is_approved = 0
    """)
    pending_admins = cur.fetchall()

    cur.execute("""
        SELECT email, first_name, last_name, role, is_approved 
        FROM users 
        WHERE role != 'super_admin'
        ORDER BY role DESC, is_approved ASC
    """)
    active_users = cur.fetchall()
    cur.close()

    return flask.render_template('super_admin_dashboard.html',
                                 pending_admins=pending_admins,
                                 active_users=active_users)


@app.route('/super-admin/approve/<email>', methods=['POST'])
def super_admin_approve(email):
    if 'user' not in flask.session or flask.session.get('role') != 'super_admin':
        return flask.redirect(flask.url_for('login_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_approved = 1 WHERE email = %s AND role = 'admin'", (email,))
    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('super_admin_dashboard'))


@app.route('/super-admin/reject/<email>', methods=['POST'])
def super_admin_reject(email):
    if 'user' not in flask.session or flask.session.get('role') != 'super_admin':
        return flask.redirect(flask.url_for('login_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM users WHERE email = %s AND role = 'admin' AND is_approved = 0", (email,))
    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('super_admin_dashboard'))


@app.route('/super-admin/delete/<email>', methods=['POST'])
def super_admin_delete_user(email):
    if 'user' not in flask.session or flask.session.get('role') != 'super_admin':
        return flask.redirect(flask.url_for('login_page'))

    if email == flask.session.get('user'):
        return "❌ Violation: You cannot purge your own Super Admin master node configuration.", 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE email = %s", (email,))
        conn.commit()
    except psycopg2.Error as e:
        cur.close()
        return f"❌ Database Execution Error: {e}", 400

    cur.close()
    return flask.redirect(flask.url_for('super_admin_dashboard'))


@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'user_email' not in flask.session:
        return flask.redirect(flask.url_for('login_page'))

    if 'profile_pic' not in flask.request.files:
        return "❌ Error: No file uploaded.", 400

    file = flask.request.files['profile_pic']
    if file.filename == '':
        return "❌ Error: No file selected.", 400

    if file and allowed_file(file.filename):
        email_prefix = flask.session['user_email'].split('@')[0]
        filename = secure_filename(f"{email_prefix}_{file.filename}")

        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE users SET profile_pic = %s WHERE email = %s',
                    (filename, flask.session['user_email']))
        conn.commit()
        cur.close()

        flask.session['profile_pic'] = filename
        return flask.redirect(flask.url_for('member_dashboard'))

    return "❌ Error: Invalid file type.", 400


@app.route('/update_interest_rate', methods=['POST'])
def update_interest_rate():
    current_role = flask.session.get('role') or flask.session.get('user_role')
    if ('user' not in flask.session and 'user_email' not in flask.session) or current_role != 'admin':
        return "Unauthorized Access!", 403

    raw_rate = flask.request.form.get('new_rate', '0').strip()
    new_rate_percent = float(raw_rate) if raw_rate else 0.0
    new_rate_decimal = new_rate_percent / 100

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("SELECT 1 FROM settings WHERE key = 'interest_rate'")
    check_row = cur.fetchone()
    if check_row:
        cur.execute(
            "UPDATE settings SET value = %s WHERE key = 'interest_rate'", (new_rate_decimal,))
    else:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES ('interest_rate', %s)", (new_rate_decimal,))

    conn.commit()
    cur.close()

    return flask.redirect(flask.url_for('admin_dashboard'))


@app.route('/admin/approve_loan/<int:request_id>')
def approve_loan(request_id):
    if 'user_email' not in flask.session or flask.session.get('user_role') != 'admin':
        return "Unauthorized Access!", 403

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute('SELECT * FROM loan_requests WHERE id = %s', (request_id,))
    request_row = cur.fetchone()
    if not request_row or request_row['status'] != 'Pending':
        cur.close()
        return "Invalid operation: Record is missing or already evaluated.", 400

    user_email = request_row['user_email']
    principal = float(request_row['amount'])
    period = int(request_row['period_months'])

    cur.execute("SELECT value FROM settings WHERE key = 'interest_rate'")
    rate_row = cur.fetchone()
    monthly_rate = float(rate_row['value']) if rate_row else 0.01

    total_interest = principal * monthly_rate * period
    total_repayment = principal + total_interest
    monthly_installment = round(total_repayment / period, 2)

    start_date = datetime.now()
    maturity_date = (start_date + timedelta(days=30 * period)
                     ).strftime("%Y-%m-%d")

    cur.execute(
        "UPDATE loan_requests SET status = 'Approved' WHERE id = %s", (request_id,))

    # PostgreSQL dialect adaptation: COALESCE handles null balance fields cleanly
    cur.execute('UPDATE users SET loan_balance = COALESCE(loan_balance, 0) + %s WHERE email = %s',
                (principal, user_email))

    cur.execute('''
        INSERT INTO active_loans (user_email, principal_amount, interest_rate, monthly_payment, maturity_date, status)
        VALUES (%s, %s, %s, %s, %s, 'Active')
    ''', (user_email, principal, monthly_rate * 100, monthly_installment, maturity_date))

    for i in range(1, period + 1):
        installment_due_date = (
            start_date + timedelta(days=30 * i)).strftime("%Y-%m-%d")
        cur.execute('''
            INSERT INTO repayment_schedules (user_email, amount, due_date, status)
            VALUES (%s, %s, %s, 'Pending')
        ''', (user_email, monthly_installment, installment_due_date))

    conn.commit()
    cur.close()
    return flask.redirect(flask.url_for('admin_dashboard'))


@app.route('/admin/reject_loan/<int:request_id>')
def reject_loan(request_id):
    if 'user_email' not in flask.session or flask.session.get('user_role') != 'admin':
        return "Unauthorized Access!", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE loan_requests SET status = 'Rejected' WHERE id = %s", (request_id,))
    conn.commit()
    cur.close()

    return flask.redirect(flask.url_for('admin_dashboard'))


USE_MPESA_SIMULATOR = True  # Set to False when connecting real Safaricom credentials

MPESA_CONSUMER_KEY = "YOUR_DARADA_CONSUMER_KEY"
MPESA_CONSUMER_SECRET = "YOUR_DARAJA_CONSUMER_SECRET"
MPESA_SHORTCODE = "174379"  # Default Safaricom Sandbox Paybill
MPESA_PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
MPESA_CALLBACK_URL = "https://yourdomain.com/api/mpesa/callback"


def get_mpesa_access_token():
    """Generates an authorization bearer token from Safaricom Daraja."""
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(
            MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET), timeout=10)
        return response.json().get("access_token")
    except Exception as e:
        print(f"M-Pesa Token Error: {e}")
        return None


@app.route('/mpesa/initiate', methods=['POST'])
def mpesa_initiate():
    """Initiates an STK Push prompt to a user's phone for deposit or loan repayment."""
    if 'user_email' not in flask.session:
        return flask.redirect(flask.url_for('login_page'))

    user_email = flask.session['user_email']
    phone = flask.request.form.get('phone', '').strip()

    raw_amount = flask.request.form.get('amount', '0').strip()
    amount = float(raw_amount) if raw_amount else 0.0

    payment_type = flask.request.form.get('payment_type', 'Deposit')
    schedule_id = flask.request.form.get('schedule_id')

    phone = re.sub(r'[\s+-]', '', phone)
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('7') or phone.startswith('1'):
        phone = '254' + phone

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    if USE_MPESA_SIMULATOR:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)

        if payment_type == 'Loan Repayment' and schedule_id:
            cur.execute(
                'UPDATE repayment_schedules SET status = \'Paid\' WHERE id = %s', (schedule_id,))

            cur.execute(
                'SELECT user_email, amount FROM repayment_schedules WHERE id = %s', (schedule_id,))
            loan_row = cur.fetchone()
            if loan_row:
                # PostgreSQL variant: GREATEST replaces scalar MAX(), COALESCE replaces IFNULL()
                cur.execute('UPDATE users SET loan_balance = GREATEST(0, COALESCE(loan_balance, 0) - %s) WHERE email = %s',
                            (amount, user_email))

            cur.execute('''
                INSERT INTO payments (user_email, amount, reference_number, status) 
                VALUES (%s, %s, %s, %s)
            ''', (user_email, amount, f"MOCK_MP_LN_{timestamp}", 'Approved'))
        else:
            cur.execute(
                'UPDATE users SET balance = balance + %s WHERE email = %s', (amount, user_email))

            cur.execute('''
                INSERT INTO payments (user_email, amount, reference_number, status) 
                VALUES (%s, %s, %s, %s)
            ''', (user_email, amount, f"MOCK_MP_DP_{timestamp}", 'Approved'))

        conn.commit()
        cur.close()
        return f"<script>alert('Simulator Mode: M-Pesa Payment of Ksh {amount} received successfully!'); window.location.href='/dashboard';</script>"

    token = get_mpesa_access_token()
    if not token:
        return "Failed to establish validation handshake with Safaricom gateway.", 500

    password = base64.b64encode(
        f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}".encode()).decode()

    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": MPESA_CALLBACK_URL,
        "AccountReference": f"SACCO-{phone[-4:]}",
        "TransactionDesc": f"SACCO Gateway {payment_type}"
    }

    try:
        response = requests.post(
            "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest", json=payload, headers=headers, timeout=12)
        res_data = response.json()

        if res_data.get("ResponseCode") == "0":
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO payments (user_email, amount, reference_number, status) 
                VALUES (%s, %s, %s, %s)
            ''', (user_email, amount, res_data.get("CheckoutRequestID"), 'Pending'))
            conn.commit()
            cur.close()
            return f"<script>alert('STK Push prompt sent to your phone! Please complete PIN authorization prompt.'); window.location.href='/dashboard';</script>"
        else:
            return f"Gateway Error: {res_data.get('ResponseDescription')}", 400
    except Exception as e:
        return f"Connection Failed: {e}", 500


if __name__ == '__main__':
    app.run(debug=True)
