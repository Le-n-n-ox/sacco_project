from flask import Blueprint, request, render_template, redirect, url_for, session
from datetime import datetime, timedelta
from psycopg2.extras import DictCursor
from extensions import get_db_connection

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def admin_dashboard():
    current_role = session.get('role') or session.get('user_role')
    if ('user' not in session and 'user_email' not in session) or current_role != 'admin':
        return redirect(url_for('auth.login_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("SELECT * FROM users WHERE role = 'member'")
    users = cur.fetchall()

    cur.execute(
        "SELECT * FROM payments WHERE LOWER(status) = 'pending' OR status IS NULL")
    pending_payments = cur.fetchall()

    cur.execute("SELECT * FROM payments ORDER BY id DESC")
    ledger_history = cur.fetchall()

    cur.execute("SELECT SUM(balance) AS total FROM users WHERE role = 'member'")
    pool_sum_row = cur.fetchone()
    pool_sum = float(
        pool_sum_row['total']) if pool_sum_row and pool_sum_row['total'] is not None else 0.0

    cur.execute(
        "SELECT * FROM loan_requests WHERE status = 'Pending' ORDER BY id DESC")
    pending_loans = cur.fetchall()

    cur.execute("SELECT value FROM settings WHERE key = 'interest_rate'")
    rate_row = cur.fetchone()
    current_rate_percent = float(rate_row['value']) * 100 if rate_row else 1.0

    cur.close()

    return render_template('admin.html',
                           members=users,
                           pending=pending_payments,
                           history=ledger_history,
                           total_pool=pool_sum,
                           pending_loans=pending_loans,
                           current_rate=current_rate_percent)


@admin_bp.route('/update_loan', methods=['POST'])
def update_loan():
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return "Unauthorized Access!", 403
    member_email = request.form.get('member_email')

    raw_loan_amount = request.form.get('loan_amount', '0').strip()
    new_loan_amount = float(raw_loan_amount) if raw_loan_amount else 0.0

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE users SET loan_balance = %s WHERE email = %s',
                (new_loan_amount, member_email))
    conn.commit()
    cur.close()
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/approve/<int:payment_id>')
def approve_payment(payment_id):
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return redirect(url_for('auth.login_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute('SELECT * FROM payments WHERE id = %s', (payment_id,))
    payment = cur.fetchone()

    if payment and (payment['status'] is None or payment['status'].lower() == 'pending'):
        cur.execute(
            "UPDATE payments SET status = 'Approved' WHERE id = %s", (payment_id,))
        cur.execute('UPDATE users SET balance = balance + %s WHERE email = %s',
                    (payment['amount'], payment['user_email']))
        conn.commit()
    cur.close()
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/reject/<int:payment_id>')
def reject_payment(payment_id):
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return redirect(url_for('auth.login_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE payments SET status = 'Rejected' WHERE id = %s", (payment_id,))
    conn.commit()
    cur.close()
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/delete_member/<string:email>')
def delete_member(email):
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return redirect(url_for('auth.login_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM users WHERE email = %s AND role = 'member'", (email,))
    cur.execute('DELETE FROM payments WHERE user_email = %s', (email,))
    conn.commit()
    cur.close()
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/update_interest_rate', methods=['POST'])
def update_interest_rate():
    current_role = session.get('role') or session.get('user_role')
    if ('user' not in session and 'user_email' not in session) or current_role != 'admin':
        return "Unauthorized Access!", 403

    raw_rate = request.form.get('new_rate', '0').strip()
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
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/approve_loan/<int:request_id>')
def approve_loan(request_id):
    if 'user_email' not in session or session.get('user_role') != 'admin':
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
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/reject_loan/<int:request_id>')
def reject_loan(request_id):
    if 'user_email' not in session or session.get('user_role') != 'admin':
        return "Unauthorized Access!", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE loan_requests SET status = 'Rejected' WHERE id = %s", (request_id,))
    conn.commit()
    cur.close()
    return redirect(url_for('admin.admin_dashboard'))
