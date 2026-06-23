import re
import base64
import requests
from flask import Blueprint, request, redirect, url_for, session, jsonify
from datetime import datetime
from requests.auth import HTTPBasicAuth
from psycopg2.extras import DictCursor
from extensions import get_db_connection

mpesa_bp = Blueprint('mpesa', __name__)

USE_MPESA_SIMULATOR = False

MPESA_CONSUMER_KEY = "I1jd5b0bjjwUGQzd0OvNz7o8A7ctjJhKVcGHNuwqCbATHfDT"
MPESA_CONSUMER_SECRET = "kQzcLFlVZPXCfDjqw69fHrI3Ij5C2dFm1OpGkXG6jkprJqOYK71bdLhecI6GmHlM"
MPESA_SHORTCODE = "174379"
MPESA_PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
MPESA_CALLBACK_URL = "https://barometer-swerve-yearly.ngrok-free.dev/api/mpesa/callback"


def get_mpesa_access_token():
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(
            MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET), timeout=10)
        return response.json().get("access_token")
    except Exception as e:
        print(f"M-Pesa Token Error: {e}")
        return None


@mpesa_bp.route('/mpesa/initiate', methods=['POST'])
def mpesa_initiate():
    if 'user_email' not in session:
        return redirect(url_for('auth.login_page'))

    user_email = session['user_email']
    phone = request.form.get('phone', '').strip()

    raw_amount = request.form.get('amount', '0').strip()
    amount = float(raw_amount) if raw_amount else 0.0

    payment_type = request.form.get('payment_type', 'Deposit')
    schedule_id = request.form.get('schedule_id')

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
                "UPDATE repayment_schedules SET status = 'Paid' WHERE id = %s", (schedule_id,))
            cur.execute(
                'SELECT user_email, amount FROM repayment_schedules WHERE id = %s', (schedule_id,))
            loan_row = cur.fetchone()
            if loan_row:
                cur.execute('UPDATE users SET loan_balance = GREATEST(0, COALESCE(loan_balance, 0) - %s) WHERE email = %s',
                            (amount, user_email))
            cur.execute("INSERT INTO payments (user_email, amount, reference_number, status) VALUES (%s, %s, %s, %s)",
                        (user_email, amount, f"MOCK_MP_LN_{timestamp}", 'Approved'))
        else:
            cur.execute(
                'UPDATE users SET balance = balance + %s WHERE email = %s', (amount, user_email))
            cur.execute("INSERT INTO payments (user_email, amount, reference_number, status) VALUES (%s, %s, %s, %s)",
                        (user_email, amount, f"MOCK_MP_DP_{timestamp}", 'Approved'))

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
            cur.execute("INSERT INTO payments (user_email, amount, reference_number, status) VALUES (%s, %s, %s, %s)",
                        (user_email, amount, res_data.get("CheckoutRequestID"), 'Pending'))
            conn.commit()
            cur.close()
            return f"<script>alert('STK Push prompt sent to your phone! Please complete PIN authorization prompt.'); window.location.href='/dashboard';</script>"
        else:
            return f"Gateway Error: {res_data.get('ResponseDescription')}", 400
    except Exception as e:
        return f"Connection Failed: {e}", 500


@mpesa_bp.route('/api/mpesa/callback', methods=['POST'])
def mpesa_callback():
    stk_data = request.get_json()
    body = stk_data.get('Body', {})
    callback_data = body.get('stkCallback', {})

    result_code = callback_data.get('ResultCode')
    checkout_request_id = callback_data.get('CheckoutRequestID')

    conn = get_db_connection()
    cur = conn.cursor()

    if result_code != 0:
        cur.execute(
            "UPDATE payments SET status = 'Failed' WHERE reference_number = %s;", (checkout_request_id,))
        conn.commit()
        cur.close()
        return jsonify({"ResultCode": 0, "ResultDescription": "Accepted"}), 200

    metadata_items = callback_data.get('CallbackMetadata', {}).get('Item', [])
    mpesa_receipt = None
    for item in metadata_items:
        if item.get('Name') == 'MpesaReceiptNumber':
            mpesa_receipt = item.get('Value')
            break

    cur.execute("SELECT user_email, amount, payment_type, schedule_id FROM payments WHERE reference_number = %s;",
                (checkout_request_id,))
    payment_record = cur.fetchone()

    if payment_record:
        user_email, amount, payment_type, schedule_id = payment_record
        cur.execute("UPDATE payments SET status = 'Completed', reference_number = %s WHERE reference_number = %s;",
                    (mpesa_receipt if mpesa_receipt else checkout_request_id, checkout_request_id))

        if payment_type == 'deposit':
            cur.execute(
                "UPDATE users SET balance = balance + %s WHERE email = %s;", (amount, user_email))
        elif payment_type == 'loan_repayment':
            cur.execute(
                "UPDATE users SET loan_balance = GREATEST(0, loan_balance - %s) WHERE email = %s;", (amount, user_email))
            if schedule_id:
                cur.execute(
                    "UPDATE repayment_schedules SET status = 'Paid' WHERE id = %s;", (schedule_id,))
        conn.commit()

    cur.close()
    return jsonify({"ResultCode": 0, "ResultDescription": "Success"}), 200
