"""db.py — PostgreSQL (Neon DB) database helpers for Amma's Farm."""

import os
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get('DATABASE_URL')


# ── Connection ────────────────────────────────────────────────────────────────

def get_conn():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")
    return psycopg2.connect(DATABASE_URL)


def dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def dictfetchone(cursor):
    if cursor.description is None:
        return None
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    return dict(zip(columns, row)) if row else None


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        icon TEXT DEFAULT '🌿',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

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
    )""")

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
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        quantity INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, product_id)
    )""")

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
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id),
        product_name TEXT,
        product_price REAL,
        quantity INTEGER,
        unit TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock_logs (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        admin_id INTEGER REFERENCES users(id),
        old_quantity INTEGER NOT NULL,
        new_quantity INTEGER NOT NULL,
        note TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT DEFAULT ''
    )""")

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


def get_user_by_email(email):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    row = dictfetchone(cur)
    cur.close()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    row = dictfetchone(cur)
    cur.close()
    conn.close()
    return row


def verify_password(user, password):
    return check_password_hash(user['password_hash'], password)


def update_user(user_id, **kwargs):
    """Update any subset of user fields. Handles password hashing if 'password' key given."""
    if not kwargs:
        return
    conn = get_conn()
    cur = conn.cursor()
    # Hash password if being updated
    if 'password' in kwargs:
        kwargs['password_hash'] = generate_password_hash(kwargs.pop('password'))
    cols = ', '.join(f"{k}=%s" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    cur.execute(f"UPDATE users SET {cols} WHERE id=%s", vals)
    conn.commit()
    cur.close()
    conn.close()


def get_all_customers(search=''):
    conn = get_conn()
    cur = conn.cursor()
    q = f"%{search}%"
    cur.execute("""
        SELECT u.*,
               COUNT(o.id)       AS order_count,
               COALESCE(SUM(o.total_amount), 0) AS total_spent
        FROM users u
        LEFT JOIN orders o ON o.user_id = u.id
        WHERE u.role = 'customer'
          AND (u.username ILIKE %s OR u.email ILIKE %s
               OR u.first_name ILIKE %s OR u.last_name ILIKE %s)
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """, (q, q, q, q))
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows


def count_customers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role='customer'")
    n = cur.fetchone()[0]
    cur.close()
    conn.close()
    return n


# ── Categories ────────────────────────────────────────────────────────────────

def get_all_categories():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories ORDER BY name")
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows


def create_category(name, icon='🌿'):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO categories (name, icon) VALUES (%s,%s) ON CONFLICT (name) DO NOTHING", (name, icon))
    conn.commit()
    cur.close()
    conn.close()


def delete_category(cat_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE products SET category_id=NULL WHERE category_id=%s", (cat_id,))
    cur.execute("DELETE FROM categories WHERE id=%s", (cat_id,))
    conn.commit()
    cur.close()
    conn.close()


# ── Products ──────────────────────────────────────────────────────────────────

def create_product(name, description='', price=0, stock_quantity=0,
                   unit='kg', low_stock_threshold=10,
                   seasonal_availability=1, category_id=None, image=''):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products
            (name, description, price, stock_quantity, unit,
             low_stock_threshold, seasonal_availability, category_id, image)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (name, description, price, stock_quantity, unit,
          low_stock_threshold, seasonal_availability, category_id, image))
    pid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return pid


def get_product(product_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, c.name AS category_name, c.icon AS category_icon
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.id = %s
    """, (product_id,))
    row = dictfetchone(cur)
    cur.close()
    conn.close()
    return row


def get_all_products(search='', category_id=None):
    """Used by admin — no pagination, returns everything."""
    conn = get_conn()
    cur = conn.cursor()
    params = []
    where = []
    if search:
        where.append("p.name ILIKE %s")
        params.append(f"%{search}%")
    if category_id:
        where.append("p.category_id = %s")
        params.append(category_id)
    sql = """
        SELECT p.*, c.name AS category_name, c.icon AS category_icon
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.created_at DESC"
    cur.execute(sql, params)
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows


def get_products(search='', available_only=False, seasonal=False,
                 ordering='name', category_id=None, page=1, per_page=12):
    """Used by customer shop — filtered + paginated."""
    conn = get_conn()
    cur = conn.cursor()
    params = []
    where = []

    if search:
        where.append("p.name ILIKE %s")
        params.append(f"%{search}%")
    if available_only:
        where.append("p.stock_quantity > 0 AND p.seasonal_availability = 1")
    if seasonal:
        where.append("p.seasonal_availability = 1")
    if category_id:
        where.append("p.category_id = %s")
        params.append(category_id)

    base_sql = """
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
    """
    if where:
        base_sql += " WHERE " + " AND ".join(where)

    # Count
    cur.execute("SELECT COUNT(*) " + base_sql, params)
    total = cur.fetchone()[0]

    order_map = {
        'name':   'p.name ASC',
        'price':  'p.price ASC',
        '-price': 'p.price DESC',
    }
    order_clause = order_map.get(ordering, 'p.name ASC')

    offset = (page - 1) * per_page
    cur.execute(
        "SELECT p.*, c.name AS category_name, c.icon AS category_icon "
        + base_sql
        + f" ORDER BY {order_clause} LIMIT %s OFFSET %s",
        params + [per_page, offset]
    )
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows, total


def update_product(product_id, **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    cur = conn.cursor()
    kwargs['updated_at'] = 'NOW()'
    # updated_at is a function call, handle separately
    set_parts = []
    vals = []
    for k, v in kwargs.items():
        if k == 'updated_at':
            set_parts.append("updated_at = NOW()")
        else:
            set_parts.append(f"{k} = %s")
            vals.append(v)
    vals.append(product_id)
    cur.execute(f"UPDATE products SET {', '.join(set_parts)} WHERE id=%s", vals)
    conn.commit()
    cur.close()
    conn.close()


def delete_product(product_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()


def count_out_of_stock():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products WHERE stock_quantity <= 0")
    n = cur.fetchone()[0]
    cur.close()
    conn.close()
    return n


def get_low_stock_products():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM products
        WHERE stock_quantity > 0 AND stock_quantity <= low_stock_threshold
        ORDER BY stock_quantity ASC
    """)
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows


# ── Cart ──────────────────────────────────────────────────────────────────────

def get_cart_count(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(quantity),0) FROM cart_items WHERE user_id=%s", (user_id,))
    n = cur.fetchone()[0]
    cur.close()
    conn.close()
    return int(n)


def get_cart_items(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT ci.id, ci.quantity,
               p.id AS product_id, p.name, p.price, p.unit,
               p.image, p.stock_quantity
        FROM cart_items ci
        JOIN products p ON p.id = ci.product_id
        WHERE ci.user_id = %s
        ORDER BY ci.created_at
    """, (user_id,))
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows


def get_cart_item(item_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cart_items WHERE id=%s AND user_id=%s", (item_id, user_id))
    row = dictfetchone(cur)
    cur.close()
    conn.close()
    return row


def get_cart_item_by_product(user_id, product_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cart_items WHERE user_id=%s AND product_id=%s", (user_id, product_id))
    row = dictfetchone(cur)
    cur.close()
    conn.close()
    return row


def add_or_update_cart(user_id, product_id, quantity_delta):
    """Add quantity_delta to existing cart item, or insert new row."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cart_items (user_id, product_id, quantity)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, product_id)
        DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
    """, (user_id, product_id, quantity_delta))
    conn.commit()
    cur.close()
    conn.close()


def update_cart_item_qty(item_id, quantity):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE cart_items SET quantity=%s WHERE id=%s", (quantity, item_id))
    conn.commit()
    cur.close()
    conn.close()


def delete_cart_item(item_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id=%s", (item_id,))
    conn.commit()
    cur.close()
    conn.close()


def clear_cart(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


# ── Orders ────────────────────────────────────────────────────────────────────

def create_order(user_id, total_amount, delivery_address, phone_number, notes, items):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders (user_id, total_amount, delivery_address, phone_number, notes)
        VALUES (%s,%s,%s,%s,%s) RETURNING id
    """, (user_id, total_amount, delivery_address, phone_number, notes))
    order_id = cur.fetchone()[0]

    for item in items:
        cur.execute("""
            INSERT INTO order_items
                (order_id, product_id, product_name, product_price, quantity, unit)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (order_id, item['product_id'], item['name'],
              item['price'], item['quantity'], item['unit']))
        cur.execute("""
            UPDATE products SET stock_quantity = stock_quantity - %s WHERE id=%s
        """, (item['quantity'], item['product_id']))

    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return order_id


def get_order_full(order_id):
    """Return order dict with nested 'items' list and customer info."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.*,
               u.username, u.email, u.first_name, u.last_name,
               u.phone_number AS user_phone
        FROM orders o
        JOIN users u ON u.id = o.user_id
        WHERE o.id = %s
    """, (order_id,))
    order = dictfetchone(cur)
    if order:
        cur.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
        order['items'] = dictfetchall(cur)
    cur.close()
    conn.close()
    return order


def get_my_orders(user_id, search='', status_filter=''):
    conn = get_conn()
    cur = conn.cursor()
    params = [user_id]
    where = ["o.user_id = %s"]
    if status_filter:
        where.append("o.order_status = %s")
        params.append(status_filter)
    if search:
        where.append("""(
            CAST(o.id AS TEXT) ILIKE %s
            OR EXISTS (
                SELECT 1 FROM order_items oi
                WHERE oi.order_id = o.id AND oi.product_name ILIKE %s
            )
        )""")
        params += [f"%{search}%", f"%{search}%"]

    cur.execute(f"""
        SELECT o.* FROM orders o
        WHERE {' AND '.join(where)}
        ORDER BY o.created_at DESC
    """, params)
    orders = dictfetchall(cur)
    for order in orders:
        cur.execute("SELECT * FROM order_items WHERE order_id=%s", (order['id'],))
        order['items'] = dictfetchall(cur)
    cur.close()
    conn.close()
    return orders


def get_all_orders(status_filter='', search=''):
    conn = get_conn()
    cur = conn.cursor()
    params = []
    where = []
    if status_filter:
        where.append("o.order_status = %s")
        params.append(status_filter)
    if search:
        where.append("""(
            CAST(o.id AS TEXT) ILIKE %s
            OR u.username ILIKE %s
            OR EXISTS (
                SELECT 1 FROM order_items oi
                WHERE oi.order_id = o.id AND oi.product_name ILIKE %s
            )
        )""")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    sql = """
        SELECT o.*, u.username FROM orders o
        JOIN users u ON u.id = o.user_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY o.created_at DESC"
    cur.execute(sql, params)
    orders = dictfetchall(cur)
    for order in orders:
        cur.execute("SELECT * FROM order_items WHERE order_id=%s", (order['id'],))
        order['items'] = dictfetchall(cur)
    cur.close()
    conn.close()
    return orders


def update_order_status(order_id, status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET order_status=%s WHERE id=%s", (status, order_id))
    conn.commit()
    cur.close()
    conn.close()


def count_orders(status=None):
    conn = get_conn()
    cur = conn.cursor()
    if status:
        cur.execute("SELECT COUNT(*) FROM orders WHERE order_status=%s", (status,))
    else:
        cur.execute("SELECT COUNT(*) FROM orders")
    n = cur.fetchone()[0]
    cur.close()
    conn.close()
    return n


def get_total_revenue():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE order_status != 'Cancelled'")
    n = cur.fetchone()[0]
    cur.close()
    conn.close()
    return float(n)


def get_recent_orders(limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.*, u.username FROM orders o
        JOIN users u ON u.id = o.user_id
        ORDER BY o.created_at DESC LIMIT %s
    """, (limit,))
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows


def get_revenue_chart_data(days=30):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT TO_CHAR(created_at::date, 'Mon DD') AS day,
               COALESCE(SUM(total_amount), 0)      AS revenue
        FROM orders
        WHERE created_at >= NOW() - INTERVAL '%s days'
          AND order_status != 'Cancelled'
        GROUP BY created_at::date, TO_CHAR(created_at::date, 'Mon DD')
        ORDER BY created_at::date
    """, (days,))
    rows = [{'day': r[0], 'revenue': float(r[1])} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


# ── Stock Logs ────────────────────────────────────────────────────────────────

def log_stock_change(product_id, admin_id, old_quantity, new_quantity, note=''):
    if old_quantity == new_quantity:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO stock_logs (product_id, admin_id, old_quantity, new_quantity, note)
        VALUES (%s,%s,%s,%s,%s)
    """, (product_id, admin_id, old_quantity, new_quantity, note))
    conn.commit()
    cur.close()
    conn.close()


def get_stock_logs(product_id=None, limit=100):
    conn = get_conn()
    cur = conn.cursor()
    if product_id:
        cur.execute("""
            SELECT sl.*, p.name AS product_name, u.username AS admin_name
            FROM stock_logs sl
            JOIN products p ON p.id = sl.product_id
            LEFT JOIN users u ON u.id = sl.admin_id
            WHERE sl.product_id = %s
            ORDER BY sl.created_at DESC LIMIT %s
        """, (product_id, limit))
    else:
        cur.execute("""
            SELECT sl.*, p.name AS product_name, u.username AS admin_name
            FROM stock_logs sl
            JOIN products p ON p.id = sl.product_id
            LEFT JOIN users u ON u.id = sl.admin_id
            ORDER BY sl.created_at DESC LIMIT %s
        """, (limit,))
    rows = dictfetchall(cur)
    cur.close()
    conn.close()
    return rows


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=%s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def set_setting(key, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings (key, value) VALUES (%s,%s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, (key, value))
    conn.commit()
    cur.close()
    conn.close()


def get_all_settings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM settings")
    rows = {r[0]: r[1] for r in cur.fetchall()}
    cur.close()
    conn.close()
    return rows