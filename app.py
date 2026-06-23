import os
import flask
from flask import Flask, render_template, redirect, url_for, session
from werkzeug.utils import secure_filename
from psycopg2.extras import DictCursor

# Import central mechanisms and Blueprint layers
from extensions import get_db_connection, close_db_connection, allowed_file, mail
from routes.auth import auth_bp
from routes.member import member_bp
from routes.admin import admin_bp
from routes.super_admin import super_admin_bp
from routes.mpesa import mpesa_bp

app = Flask(__name__)
app.secret_key = 'super_secret_sacco_key_replace_this_in_production'

# 📧 EMAIL CONFIGURATION
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'lexwanys@gmail.com'
app.config['MAIL_PASSWORD'] = 'wjfy bqaz tssp opad'
app.config['MAIL_DEFAULT_SENDER'] = ('WealthArc SACCO', 'lexwanys@gmail.com')

# Bind utility context plugins
mail.init_app(app)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register Blueprint layers
app.register_blueprint(auth_bp)
app.register_blueprint(member_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(super_admin_bp)
app.register_blueprint(mpesa_bp)

# Automatic context clean up link hook
app.teardown_appcontext(close_db_connection)

# =====================================================================
# 🩹 TEMPLATE BACKWARD-COMPATIBILITY PATCHES
# =====================================================================
# These functions act as safety anchors. If an old HTML template calls
# url_for('login_page') instead of url_for('auth.login_page'), these
# catch the request and seamlessly bridge it to prevent a BuildError crash.


@app.route('/legacy-login-route')
def login_page():
    return redirect(url_for('auth.login_page'))


@app.route('/legacy-admin-route')
def admin_dashboard():
    return redirect(url_for('admin.admin_dashboard'))


@app.route('/legacy-member-route')
def member_dashboard():
    return redirect(url_for('member.member_dashboard'))


@app.route('/legacy-super-admin-route')
def super_admin_dashboard():
    return redirect(url_for('super_admin.super_admin_dashboard'))


# =====================================================================
# GLOBAL GENERAL CORE ROUTING
# =====================================================================

@app.route('/')
def home_page():
    """
    Renders the central SACCO welcome hub page (home.html), dynamically
    calculating financial pools directly from live production schemas.
    """
    # 1. Guard check: secure user session entry context
    if 'user' not in session and 'user_email' not in session:
        return redirect(url_for('auth.login_page'))

    current_user_email = session.get('user') or session.get('user_email')

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)

        # 2. Extract profile details for the authenticated user
        cur.execute('SELECT * FROM users WHERE email = %s',
                    (current_user_email,))
        user = cur.fetchone()

        if user is None:
            session.clear()
            return redirect(url_for('auth.login_page'))

        pending_admins = []

        # 3. Handle Super Admin Queue using your integer 'is_approved' flag (0 = Pending)
        if user['role'] == 'super_admin':
            cur.execute(
                "SELECT * FROM users WHERE role = 'admin' AND is_approved = 0")
            pending_admins = cur.fetchall()

        # 4. Calculate Total Liquid Shares using the balance field from your users table
        cur.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
        pool_res = cur.fetchone()
        # Formats the raw numeric value into a clean, comma-separated currency string
        total_pool = f"{float(pool_res[0]):,}"

        # 5. Calculate Total Advanced Loans using the loan_balance field from your users table
        cur.execute("SELECT COALESCE(SUM(loan_balance), 0) FROM users")
        loan_res = cur.fetchone()
        total_loans = f"{float(loan_res[0]):,}"

        # Clean connection closure
        cur.close()
        conn.close()

        # 6. Push real data layers safely to the front-end rendering engine
        return render_template(
            'home.html',
            user=user,
            pending_admins=pending_admins,
            total_pool=total_pool,
            total_loans=total_loans
        )

    except Exception as db_error:
        print(
            f"❌ [SCHEMA MATCH ERROR] Central Hub calculation execution failed: {db_error}")
        return f"Database Error: {db_error}", 500


@app.route('/calculator')
def loan_calculator():
    return render_template('calculator.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login_page'))


@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_page'))

    if 'profile_pic' not in flask.request.files:
        return "❌ Error: No file uploaded.", 400

    file = flask.request.files['profile_pic']
    if file.filename == '':
        return "❌ Error: No file selected.", 400

    if file and allowed_file(file.filename):
        email_prefix = session['user_email'].split('@')[0]
        filename = secure_filename(f"{email_prefix}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE users SET profile_pic = %s WHERE email = %s',
                    (filename, session['user_email']))
        conn.commit()
        cur.close()

        session['profile_pic'] = filename
        return redirect(url_for('member.member_dashboard'))

    return "❌ Error: Invalid file type.", 400


if __name__ == '__main__':
    app.run(debug=True)
