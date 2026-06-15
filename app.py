import os
import sqlite3
import re
import random
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
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
    if 'user' not in session and 'user_email' not in session:
        return redirect(url_for('login_page'))

    current_user_email = session.get('user') or session.get('user_email')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?',
                        (current_user_email,)).fetchone()
    conn.close()

    if user is None:
        session.clear()
        return redirect(url_for('login_page'))

    if user['role'] == 'super_admin':
        return redirect(url_for('super_admin_dashboard'))
    elif user['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('member_dashboard'))

# =====================================================================
# 2. SEAMLESS AUTHENTICATION & SECURITY HOOKS
# =====================================================================


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password')

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        # 🔍 TERMINAL DIAGNOSTICS: Prints directly to your console to detect database state mismatches
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
            if user['role'] == 'admin' and int(user['is_approved']) != 1:
                return "Account pending approval from Super Admin.", 403

            # 🔐 UNIFIED SESSION ARRAYS: Populates both styles safely
            session['user'] = user['email']
            session['user_email'] = user['email']
            session['role'] = user['role']
            session['user_role'] = user['role']
            return redirect(url_for('home_page'))

        # If password hash check fails, reload login page cleanly
        return redirect(url_for('login_page'))

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
        existing_user = conn.execute(
            'SELECT email FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if existing_user:
            return "❌ Error: An account with that email already exists!", 400

        verification_code = str(random.randint(100000, 999999))

        session['temp_registration'] = {
            'email': email, 'password': password, 'first_name': first_name,
            'last_name': last_name, 'phone': phone, 'dob': dob, 'role': target_role
        }
        session['verification_code'] = verification_code

        try:
            msg = Message(
                "WealthArc SACCO - Verify Your Account Registration", recipients=[email])
            msg.body = f"Hello {first_name},\n\nThank you for signing up with WealthArc SACCO.\nYour 2-Step Verification code is: {verification_code}\n\nPlease enter this code on the verification screen to activate your account."
            mail.send(msg)
        except Exception as e:
            return f"❌ Failed to send verification email. Error: {e}", 500

        return redirect(url_for('verify_code_page'))

    return render_template('register.html')


@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code_page():
    if 'temp_registration' not in session or 'verification_code' not in session:
        return redirect(url_for('register_page'))

    if request.method == 'POST':
        user_input_code = request.form.get('code', '').strip()

        if user_input_code == session.get('verification_code'):
            reg_data = session['temp_registration']
            approval_status = 0 if reg_data['role'] == 'admin' else 1

            secure_hashed_password = generate_password_hash(
                reg_data['password'])

            conn = get_db_connection()
            try:
                conn.execute("""
                    INSERT INTO users (email, password, role, first_name, last_name, phone, dob, is_approved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (reg_data['email'], secure_hashed_password, reg_data['role'],
                      reg_data['first_name'], reg_data['last_name'], reg_data['phone'], reg_data['dob'], approval_status))
                conn.commit()
            except sqlite3.Error as database_err:
                conn.close()
                return f"❌ Database Save Error: {database_err}", 400
            conn.close()

            session.pop('temp_registration', None)
            session.pop('verification_code', None)

            if reg_data['role'] == 'admin':
                return "🎉 Email Verified! Your administrator account is now pending clearance from the Super Admin."

            return redirect(url_for('login_page'))
        else:
            return render_template('verify.html',
                                   email=session['temp_registration']['email'],
                                   error="❌ Invalid Verification Code! Please try again.")

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
    rate_row = conn.execute(
        'SELECT value FROM settings WHERE key = "interest_rate"').fetchone()
    interest_rate = rate_row['value'] if rate_row else 0.01
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
    return render_template('member.html',
                           user=user,
                           payments=payments,
                           total_pool=total_pool,
                           total_loans=total_loans,
                           community=community_members,
                           interest_rate=interest_rate)


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
    current_role = session.get('role') or session.get('user_role')
    if ('user' not in session and 'user_email' not in session) or current_role != 'admin':
        return redirect(url_for('login_page'))

    conn = get_db_connection()
    users = conn.execute(
        "SELECT * FROM users WHERE role = 'member'").fetchall()
    pending_payments = conn.execute("""
        SELECT * FROM payments 
        WHERE status = 'Pending' OR status = 'pending' OR status IS NULL
    """).fetchall()
    ledger_history = conn.execute(
        "SELECT * FROM payments ORDER BY id DESC").fetchall()
    pool_sum = conn.execute(
        'SELECT SUM(balance) FROM users WHERE role = "member"').fetchone()[0] or 0.0
    conn.close()

    return render_template('admin.html',
                           members=users,
                           pending=pending_payments,
                           history=ledger_history,
                           total_pool=pool_sum)


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

    if payment and (payment['status'] == 'Pending' or payment['status'] == 'pending' or payment['status'] is None):
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


@app.route('/calculator')
def loan_calculator():
    return render_template('calculator.html')


@app.route('/super-admin-dashboard')
def super_admin_dashboard():
    if 'user' not in session or session.get('role') != 'super_admin':
        return redirect(url_for('login_page'))

    conn = get_db_connection()
    pending_admins = conn.execute("""
        SELECT email, first_name, last_name, phone, dob 
        FROM users 
        WHERE role = 'admin' AND is_approved = 0
    """).fetchall()

    active_users = conn.execute("""
        SELECT email, first_name, last_name, role, is_approved 
        FROM users 
        WHERE role != 'super_admin'
        ORDER BY role DESC, is_approved ASC
    """).fetchall()
    conn.close()

    return render_template('super_admin_dashboard.html',
                           pending_admins=pending_admins,
                           active_users=active_users)


@app.route('/super-admin/approve/<email>', methods=['POST'])
def super_admin_approve(email):
    if 'user' not in session or session.get('role') != 'super_admin':
        return redirect(url_for('login_page'))

    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET is_approved = 1 WHERE email = ? AND role = 'admin'", (email,))
    conn.commit()
    conn.close()
    return redirect(url_for('super_admin_dashboard'))


@app.route('/super-admin/reject/<email>', methods=['POST'])
def super_admin_reject(email):
    if 'user' not in session or session.get('role') != 'super_admin':
        return redirect(url_for('login_page'))

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM users WHERE email = ? AND role = 'admin' AND is_approved = 0", (email,))
    conn.commit()
    conn.close()
    return redirect(url_for('super_admin_dashboard'))


@app.route('/super-admin/delete/<email>', methods=['POST'])
def super_admin_delete_user(email):
    if 'user' not in session or session.get('role') != 'super_admin':
        return redirect(url_for('login_page'))

    if email == session.get('user'):
        return "❌ Violation: You cannot purge your own Super Admin master node configuration.", 400

    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM users WHERE email = ?", (email,))
        conn.commit()
    except sqlite3.Error as e:
        conn.close()
        return f"❌ Database Execution Error: {e}", 400

    conn.close()
    return redirect(url_for('super_admin_dashboard'))


@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'user_email' not in session:
        return redirect(url_for('login_page'))

    if 'profile_pic' not in request.files:
        return "❌ Error: No file uploaded.", 400

    file = request.files['profile_pic']
    if file.filename == '':
        return "❌ Error: No file selected.", 400

    if file and allowed_file(file.filename):
        email_prefix = session['user_email'].split('@')[0]
        filename = secure_filename(f"{email_prefix}_{file.filename}")

        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        conn.execute('UPDATE users SET profile_pic = ? WHERE email = ?',
                     (filename, session['user_email']))
        conn.commit()
        conn.close()

        session['profile_pic'] = filename
        return redirect(url_for('member_dashboard'))

    return "❌ Error: Invalid file type.", 400


@app.route('/update_interest_rate', methods=['POST'])
def update_interest_rate():
    if session.get('user_role') != 'admin':
        return "Unauthorized", 403

    new_rate_percent = float(request.form['new_rate'])
    new_rate_decimal = new_rate_percent / 100

    conn = get_db_connection()
    conn.execute(
        'UPDATE settings SET value = ? WHERE key = "interest_rate"', (new_rate_decimal,))
    conn.commit()
    conn.close()

    return redirect(url_for('member_dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
