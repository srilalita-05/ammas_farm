"""db.py — PostgreSQL (Neon DB) database helpers for Amma's Farm."""

import os
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash

# Use Neon DB URL from environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')


# ── Connection ────────────────────────────────────────────────────────────────

def get_conn():
    """Return a new database connection"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def dictfetchall(cursor):
    """Return all rows as list of dicts"""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def dictfetchone(cursor):
    """Return single row as dict"""
    if cursor.description is None:
        return None
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    return dict(zip(columns, row)) if row else None


# ── Schema / Initialization ────────────────────────────────────────────────────

def init_db():
    """Create tables if they do not exist"""
    conn = get_conn()
    cur = conn.cursor()

    # Categories
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        icon TEXT DEFAULT '🌿',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        first_name TEXT DEFAULT '',
        last_name TEXT DEFAULT '',
        phone_number TEXT DEFAULT '',
        address TEXT DEFAULT '',
        role TEXT DEFAULT 'customer',
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Products
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price REAL NOT NULL,
        stock_quantity INTEGER DEFAULT 0,
        seasonal_availability INTEGER DEFAULT 1,
        image TEXT DEFAULT '',
        unit TEXT DEFAULT 'kg',
        low_stock_threshold INTEGER DEFAULT 10,
        category_id INTEGER REFERENCES categories(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Cart items
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        quantity INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, product_id)
    )
    """)

    # Orders
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        total_amount REAL NOT NULL,
        order_status TEXT DEFAULT 'Pending',
        delivery_address TEXT DEFAULT '',
        phone_number TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Order items
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id),
        product_name TEXT,
        product_price REAL,
        quantity INTEGER,
        unit TEXT
    )
    """)

    # Stock logs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_logs (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        admin_id INTEGER REFERENCES users(id),
        old_quantity INTEGER NOT NULL,
        new_quantity INTEGER NOT NULL,
        note TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Settings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT DEFAULT ''
    )
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully 🌱")


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username, email, password, role='customer'):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (%s,%s,%s,%s)",
        (username, email, generate_password_hash(password), role)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_user_by_username(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    row = dictfetchone(cur)
    cur.close()
    conn.close()
    return row


def verify_password(user, password):
    return check_password_hash(user['password_hash'], password)


# ── Products ──────────────────────────────────────────────────────────────────

def create_product(name, description, price, stock_quantity, unit='kg', category_id=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO products (name, description, price, stock_quantity, unit, category_id)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
        """,
        (name, description, price, stock_quantity, unit, category_id)
    )
    pid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return pid


def get_all_products():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products ORDER BY created_at DESC")
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows


# ── Orders ────────────────────────────────────────────────────────────────────

def create_order(user_id, total_amount, delivery_address, phone_number, notes, items):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, total_amount, delivery_address, phone_number, notes) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (user_id, total_amount, delivery_address, phone_number, notes)
    )
    order_id = cur.fetchone()[0]

    for item in items:
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, product_name, product_price, quantity, unit) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (order_id, item['product_id'], item['name'], item['price'], item['quantity'], item['unit'])
        )
        cur.execute(
            "UPDATE products SET stock_quantity = stock_quantity - %s WHERE id=%s",
            (item['quantity'], item['product_id'])
        )

    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return order_id