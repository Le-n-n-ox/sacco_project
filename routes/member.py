import psycopg2
from flask import Blueprint, request, render_template, redirect, url_for, session
from datetime import datetime
from psycopg2.extras import DictCursor
from extensions import get_db_connection

member_bp = Blueprint('member', __name__)


@member_bp.route('/dashboard')
def member_dashboard():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_page'))

    email = session['user_email']
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

    cur.execute("SELECT SUM(balance) AS total FROM users WHERE role = 'member'")
    total_pool_row = cur.fetchone()
    total_pool = float(
        total_pool_row['total']) if total_pool_row and total_pool_row['total'] is not None else 0.0

    cur.execute(
        "SELECT SUM(loan_balance) AS total FROM users WHERE role = 'member'")
    total_loans_row = cur.fetchone()
    total_loans = float(
        total_loans_row['total']) if total_loans_row and total_loans_row['total'] is not None else 0.0

    cur.execute("SELECT first_name, last_name, balance, loan_balance, profile_pic FROM users WHERE role = 'member' ORDER BY balance DESC")
    community_members = cur.fetchall()

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
        loan_requests = []
        active_loan_query = None
        repayment_schedule = []

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
    return render_template('member.html',
                           user=user,
                           payments=payments,
                           total_pool=total_pool,
                           total_loans=total_loans,
                           community=community_members,
                           interest_rate=interest_rate,
                           loan_requests=loan_requests,
                           active_loan=active_loan,
                           repayment_schedule=repayment_schedule)


@member_bp.route('/apply_loan', methods=['POST'])
def apply_loan():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_page'))

    email = session['user_email']
    raw_amount = request.form.get('loan_amount', '0').strip()
    amount = float(raw_amount) if raw_amount else 0.0

    raw_period = request.form.get('loan_period', '12').strip()
    period = int(raw_period) if raw_period else 12

    purpose = request.form.get('loan_purpose', '').strip()
    date_applied = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO loan_requests (user_email, amount, period_months, purpose, status, date_applied)
            VALUES (%s, %s, %s, %s, 'Pending', %s)
        ''', (email, amount, period, purpose, date_applied))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Warning: Loan entry failure: {e}")
    finally:
        cur.close()

    return redirect(url_for('member.member_dashboard'))


@member_bp.route('/submit_payment', methods=['POST'])
def submit_payment():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_page'))
    email = session['user_email']

    raw_amount = request.form.get('amount', '0').strip()
    amount = float(raw_amount) if raw_amount else 0.0
    ref_num = request.form.get('reference_number', '').upper().strip()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO payments (user_email, amount, reference_number) VALUES (%s, %s, %s)',
                (email, amount, ref_num))
    conn.commit()
    cur.close()
    return redirect(url_for('member.member_dashboard'))
