from flask import Blueprint, request, render_template, redirect, url_for, session
from psycopg2.extras import DictCursor
from extensions import get_db_connection

super_admin_bp = Blueprint('super_admin', __name__)


@super_admin_bp.route('/approve_admin/<string:email>')
def approve_admin(email):
    if 'user_email' not in session or session.get('user_role') != 'super_admin':
        return "Unauthorized Override!", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_approved = 1 WHERE email = %s AND role = 'admin'", (email,))
    conn.commit()
    cur.close()
    return redirect(url_for('home_page'))


@super_admin_bp.route('/deny_admin/<string:email>')
def deny_admin(email):
    if 'user_email' not in session or session.get('user_role') != 'super_admin':
        return "Unauthorized Override!", 403

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM users WHERE email = %s AND role = 'admin' AND is_approved = 0", (email,))
    conn.commit()
    cur.close()
    return redirect(url_for('home_page'))


@super_admin_bp.route('/super-admin-dashboard')
def super_admin_dashboard():
    if 'user' not in session or session.get('role') != 'super_admin':
        return redirect(url_for('auth.login_page'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute(
        "SELECT email, first_name, last_name, phone, dob FROM users WHERE role = 'admin' AND is_approved = 0")
    pending_admins = cur.fetchall()

    cur.execute("SELECT email, first_name, last_name, role, is_approved FROM users WHERE role != 'super_admin' ORDER BY role DESC, is_approved ASC")
    active_users = cur.fetchall()
    cur.close()

    return render_template('super_admin_dashboard.html', pending_admins=pending_admins, active_users=active_users)


@super_admin_bp.route('/super-admin/approve/<email>', methods=['POST'])
def super_admin_approve(email):
    if 'user' not in session or session.get('role') != 'super_admin':
        return redirect(url_for('auth.login_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_approved = 1 WHERE email = %s AND role = 'admin'", (email,))
    conn.commit()
    cur.close()
    return redirect(url_for('super_admin.super_admin_dashboard'))


@super_admin_bp.route('/super-admin/reject/<email>', methods=['POST'])
def super_admin_reject(email):
    if 'user' not in session or session.get('role') != 'super_admin':
        return redirect(url_for('auth.login_page'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM users WHERE email = %s AND role = 'admin' AND is_approved = 0", (email,))
    conn.commit()
    cur.close()
    return redirect(url_for('super_admin.super_admin_dashboard'))


@super_admin_bp.route('/super-admin/delete/<email>', methods=['POST'])
def super_admin_delete_user(email):
    if 'user' not in session or session.get('role') != 'super_admin':
        return redirect(url_for('auth.login_page'))

    if email == session.get('user'):
        return "❌ Violation: You cannot purge your own Super Admin master node configuration.", 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE email = %s", (email,))
        conn.commit()
    except Exception as e:
        cur.close()
        return f"❌ Database Execution Error: {e}", 400

    cur.close()
    return redirect(url_for('super_admin.super_admin_dashboard'))
