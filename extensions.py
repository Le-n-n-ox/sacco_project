import os
import psycopg2
from flask import g
from flask_mail import Mail

# Initialize mail globally without binding to an app yet
mail = Mail()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def get_db_connection():
    """Opens a safe, isolated database connection attached to the current request context targeting PostgreSQL."""
    if 'db' not in g:
        g.db = psycopg2.connect(
            host="localhost",
            database="sacco_project",
            user="postgres",
            password="1111",  # Your pgAdmin installation password
            port="5432"
        )
    return g.db


def close_db_connection(exception=None):
    """Fail-safe hook that automatically closes connections, even if a route crashes."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
