import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_sacco_key_replace_this_in_production'

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
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()

        if user:
            # 🔒 VERIFICATION ENFORCEMENT GATE:
            if user['role'] == 'admin' and user['is_approved'] == 0:
                return "⚠️ Access Denied: Your administrator account is currently pending clearance from the Super Admin dashboard.", 403

            session['user_email'] = user['email']
            session['user_role'] = user['role']
            return redirect(url_for('home_page'))
        else:
            return "Invalid Credentials! Please try again.", 401

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        dob = request.form.get('dob')
        target_role = request.form.get('role', 'member')

        # New admin signups drop in locked down (0), standard members auto-pass (1)
        approval_status = 0 if target_role == 'admin' else 1

        profile_pic_filename = 'default.png'
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{email.replace('@', '_').replace('.', '_')}_{filename}"
                file.save(os.path.join(
                    app.config['UPLOAD_FOLDER'], unique_filename))
                profile_pic_filename = unique_filename

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO users (email, password, role, balance, loan_balance, first_name, last_name, phone, dob, profile_pic, is_approved)
                VALUES (?, ?, ?, 0.0, 0.0, ?, ?, ?, ?, ?, ?)
            """, (email, password, target_role, first_name, last_name, phone, dob, profile_pic_filename, approval_status))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Error: An account with that email address already exists!", 400

        conn.close()

        if target_role == 'admin':
            return "🎉 Account requested successfully! Please notify your Super Admin to approve your terminal profile before logging in."
        return redirect(url_for('login_page'))

    return render_template('register.html')

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
