import re
import random
import flask
from flask import Blueprint, request, render_template, redirect, url_for, session
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import DictCursor
from extensions import get_db_connection, mail

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

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
            session['user'] = user['email']
            session['user_email'] = user['email']
            session['role'] = user['role']
            session['user_role'] = user['role']
            return redirect(url_for('home_page'))

        return redirect(url_for('auth.login_page'))

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        dob = request.form.get('dob', '')
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
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute('SELECT email FROM users WHERE email = %s', (email,))
        existing_user = cur.fetchone()
        cur.close()

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

        return redirect(url_for('auth.verify_code_page'))

    return render_template('register.html')


@auth_bp.route('/verify-code', methods=['GET', 'POST'])
def verify_code_page():
    if 'temp_registration' not in session or 'verification_code' not in session:
        return redirect(url_for('auth.register_page'))

    if request.method == 'POST':
        user_input_code = request.form.get('code', '').strip()

        if user_input_code == session.get('verification_code'):
            reg_data = session['temp_registration']
            approval_status = 0 if reg_data['role'] == 'admin' else 1

            secure_hashed_password = generate_password_hash(
                reg_data['password'], method='pbkdf2:sha256')

            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO users (email, password, role, first_name, last_name, phone, dob, is_approved)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (reg_data['email'], secure_hashed_password, reg_data['role'],
                      reg_data['first_name'], reg_data['last_name'], reg_data['phone'], reg_data['dob'], approval_status))
                conn.commit()
            except Exception as database_err:
                cur.close()
                return f"❌ Database Save Error: {database_err}", 400
            cur.close()

            session.pop('temp_registration', None)
            session.pop('verification_code', None)

            if reg_data['role'] == 'admin':
                return "🎉 Email Verified! Your administrator account is now pending clearance from the Super Admin."

            return redirect(url_for('auth.login_page'))
        else:
            return render_template('verify.html',
                                   email=session['temp_registration']['email'],
                                   error="❌ Invalid Verification Code! Please try again.")

    return render_template('verify.html', email=session['temp_registration']['email'])
