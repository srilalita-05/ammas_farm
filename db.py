"""db.py — PostgreSQL (Neon DB) database helpers for Amma's Farm."""

import os, json
from datetime import datetime, date
import psycopg2
import psycopg2.pool
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get('DATABASE_URL')

# Allowed columns for updates (whitelists to prevent SQL injection via column names)
ALLOWED_USER_COLUMNS = {
    'username', 'email', 'first_name', 'last_name',
    'phone_number', 'address', 'role', 'password_hash'
}

ALLOWED_PRODUCT_COLUMNS = {
    'name', 'description', 'price', 'stock_quantity',
    'seasonal_availability', 'image', 'unit', 'low_stock_threshold',
    'category_id'
}


# ── Connection Pool ───────────────────────────────────────────────────────────

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not set")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL
        )
    return _pool

def get_conn():
    return get_pool().getconn()

def release_conn(conn):
    """Return connection to pool instead of closing it."""
    if conn:
        get_pool().putconn(conn)


# ── Serialization helpers ─────────────────────────────────────────────────────

def _serialize(val):
    """Convert Python types that Jinja2 can't slice/format into plain strings."""
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, date):
        return val.strftime('%Y-%m-%d')
    return val


def dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [
        {col: _serialize(val) for col, val in zip(columns, row)}
        for row in cursor.fetchall()
    ]


def dictfetchone(cursor):
    if cursor.description is None:
        return None
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    if not row:
        return None
    return {col: _serialize(val) for col, val in zip(columns, row)}


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    try:
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

        cur.execute("SELECT 1 FROM pg_constraint WHERE conname = 'stock_non_negative'")
        if cur.fetchone() is None:
            try:
                cur.execute("ALTER TABLE products ADD CONSTRAINT stock_non_negative CHECK (stock_quantity >= 0)")
            except Exception:
                pass

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

        # ✅ FIXED: Audit log table (Issue #12)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            details JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        conn.commit()
        cur.close()
        print("Database initialized successfully 🌱")
    finally:
        release_conn(conn)


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username, email, password, role='customer'):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (%s,%s,%s,%s)",
            (username, email, generate_password_hash(password), role)
        )
        conn.commit()
        cur.close()
    except psycopg2.IntegrityError:
        # ✅ FIXED: Re-raise for app.py to catch (Issue #3)
        conn.rollback()
        cur.close()
        raise
    finally:
        release_conn(conn)


def get_user_by_username(username):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        row = dictfetchone(cur)
        cur.close()
        return row
    finally:
        release_conn(conn)


def get_user_by_email(email):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        row = dictfetchone(cur)
        cur.close()
        return row
    finally:
        release_conn(conn)


def get_user_by_id(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        row = dictfetchone(cur)
        cur.close()
        return row
    finally:
        release_conn(conn)


def verify_password(user, password):
    return check_password_hash(user['password_hash'], password)


def update_user(user_id, **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        if 'password' in kwargs:
            kwargs['password_hash'] = generate_password_hash(kwargs.pop('password'))

        valid_items = {k: v for k, v in kwargs.items() if k in ALLOWED_USER_COLUMNS}
        if not valid_items:
            cur.close()
            return

        cols = ', '.join(f"{k}=%s" for k in valid_items)
        vals = list(valid_items.values()) + [user_id]
        cur.execute(f"UPDATE users SET {cols} WHERE id=%s", vals)
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def get_all_customers(search=''):
    conn = get_conn()
    try:
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
        return rows
    finally:
        release_conn(conn)


def count_customers():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE role='customer'")
        n = cur.fetchone()[0]
        cur.close()
        return n
    finally:
        release_conn(conn)


# ── Categories ────────────────────────────────────────────────────────────────

def get_all_categories():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories ORDER BY name")
        rows = dictfetchall(cur)
        cur.close()
        return rows
    finally:
        release_conn(conn)

def get_category_by_id(cat_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM categories WHERE id=%s", (cat_id,))
        row = dictfetchone(cur)
        cur.close()
        return row
    finally:
        release_conn(conn)

def create_category(name, icon='🌿'):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO categories (name, icon) VALUES (%s,%s) ON CONFLICT (name) DO NOTHING",
            (name, icon)
        )
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def delete_category(cat_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE products SET category_id=NULL WHERE category_id=%s", (cat_id,))
        cur.execute("DELETE FROM categories WHERE id=%s", (cat_id,))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


# ── Products ──────────────────────────────────────────────────────────────────

def create_product(name, description='', price=0, stock_quantity=0,
                   unit='kg', low_stock_threshold=10,
                   seasonal_availability=1, category_id=None, image=''):
    conn = get_conn()
    try:
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
        return pid
    finally:
        release_conn(conn)


def get_product(product_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.*, c.name AS category_name, c.icon AS category_icon
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.id = %s
        """, (product_id,))
        row = dictfetchone(cur)
        cur.close()
        return row
    finally:
        release_conn(conn)


def get_all_products(search='', category_id=None):
    """Used by admin — no pagination, returns everything."""
    conn = get_conn()
    try:
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
        return rows
    finally:
        release_conn(conn)


def count_products():
    """Fast COUNT(*) instead of loading all rows."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        n = cur.fetchone()[0]
        cur.close()
        return n
    finally:
        release_conn(conn)


def get_products(search='', available_only=False, seasonal=False,
                 ordering='name', category_id=None, page=1, per_page=12):
    """Used by customer shop — filtered + paginated."""
    conn = get_conn()
    try:
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
        return rows, total
    finally:
        release_conn(conn)


def update_product(product_id, **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        kwargs.pop('updated_at', None)

        valid_items = {k: v for k, v in kwargs.items() if k in ALLOWED_PRODUCT_COLUMNS}
        if not valid_items:
            cur.close()
            return

        set_parts = ["updated_at = NOW()"]
        vals = []
        for k, v in valid_items.items():
            set_parts.append(f"{k} = %s")
            vals.append(v)
        vals.append(product_id)
        cur.execute(f"UPDATE products SET {', '.join(set_parts)} WHERE id=%s", vals)
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def delete_product(product_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def count_out_of_stock():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products WHERE stock_quantity <= 0")
        n = cur.fetchone()[0]
        cur.close()
        return n
    finally:
        release_conn(conn)


def get_low_stock_products():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM products
            WHERE stock_quantity > 0 AND stock_quantity <= low_stock_threshold
            ORDER BY stock_quantity ASC
        """)
        rows = dictfetchall(cur)
        cur.close()
        return rows
    finally:
        release_conn(conn)


# ── Cart ──────────────────────────────────────────────────────────────────────

def get_cart_count(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(quantity),0) FROM cart_items WHERE user_id=%s", (user_id,))
        n = cur.fetchone()[0]
        cur.close()
        return int(n)
    finally:
        release_conn(conn)


def get_cart_items(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        # ✅ FIXED: Changed JOIN to LEFT JOIN (Issue #8)
        cur.execute("""
            SELECT ci.id, ci.quantity,
                   p.id AS product_id, p.name, p.price, p.unit,
                   p.image, p.stock_quantity
            FROM cart_items ci
            LEFT JOIN products p ON p.id = ci.product_id
            WHERE ci.user_id = %s
            ORDER BY ci.created_at
        """, (user_id,))
        rows = dictfetchall(cur)
        cur.close()
        return rows
    finally:
        release_conn(conn)


def get_cart_item(item_id, user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cart_items WHERE id=%s AND user_id=%s", (item_id, user_id))
        row = dictfetchone(cur)
        cur.close()
        return row
    finally:
        release_conn(conn)


def get_cart_item_by_product(user_id, product_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM cart_items WHERE user_id=%s AND product_id=%s",
            (user_id, product_id)
        )
        row = dictfetchone(cur)
        cur.close()
        return row
    finally:
        release_conn(conn)


def add_or_update_cart(user_id, product_id, quantity_delta):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO cart_items (user_id, product_id, quantity)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, product_id)
            DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
        """, (user_id, product_id, quantity_delta))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def update_cart_item_qty(item_id, quantity):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE cart_items SET quantity=%s WHERE id=%s", (quantity, item_id))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def delete_cart_item(item_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cart_items WHERE id=%s", (item_id,))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def clear_cart(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


# ── Orders ────────────────────────────────────────────────────────────────────

def create_order(user_id, total_amount, delivery_address, phone_number, notes, items):
    conn = get_conn()
    try:
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

            # ✅ FIXED: Better error message (Issue #2)
            cur.execute("""
                UPDATE products
                SET stock_quantity = stock_quantity - %s
                WHERE id = %s AND stock_quantity >= %s
            """, (item['quantity'], item['product_id'], item['quantity']))

            if cur.rowcount == 0:
                conn.rollback()
                cur.close()
                product = get_product(item['product_id'])
                product_name = product['name'] if product else f"Product {item['product_id']}"
                raise ValueError(f"{product_name} is out of stock. Please remove it from your cart and try again.")

        cur.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))
        conn.commit()
        cur.close()
        return order_id
    finally:
        release_conn(conn)


def get_order_full(order_id):
    conn = get_conn()
    try:
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
        return order
    finally:
        release_conn(conn)


def get_my_orders(user_id, search='', status_filter=''):
    """Fixed: uses a single JOIN query instead of N+1 queries."""
    conn = get_conn()
    try:
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
            SELECT o.*, oi.id AS oi_id, oi.product_name, oi.product_price,
                   oi.quantity AS oi_qty, oi.unit AS oi_unit, oi.product_id AS oi_product_id
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE {' AND '.join(where)}
            ORDER BY o.created_at DESC, oi.id
        """, params)

        rows = cur.fetchall()
        cols = [col[0] for col in cur.description]
        cur.close()

        orders = _group_orders_with_items(rows, cols)
        return orders
    finally:
        release_conn(conn)


def get_all_orders(status_filter='', search=''):
    """Fixed: uses a single JOIN query instead of N+1 queries."""
    conn = get_conn()
    try:
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
            SELECT o.*, u.username,
                   oi.id AS oi_id, oi.product_name, oi.product_price,
                   oi.quantity AS oi_qty, oi.unit AS oi_unit, oi.product_id AS oi_product_id
            FROM orders o
            JOIN users u ON u.id = o.user_id
            LEFT JOIN order_items oi ON oi.order_id = o.id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY o.created_at DESC, oi.id"

        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [col[0] for col in cur.description]
        cur.close()

        orders = _group_orders_with_items(rows, cols)
        return orders
    finally:
        release_conn(conn)


def _group_orders_with_items(rows, cols):
    """
    Helper: collapse JOIN rows (one per order_item) back into
    a list of order dicts, each with an 'items' list.
    """
    from collections import OrderedDict
    orders_map = OrderedDict()
    item_cols  = {'oi_id', 'product_name', 'product_price', 'oi_qty', 'oi_unit', 'oi_product_id'}

    for row in rows:
        record = {col: _serialize(val) for col, val in zip(cols, row)}
        oid = record['id']

        if oid not in orders_map:
            order = {k: v for k, v in record.items() if k not in item_cols}
            order['items'] = []
            orders_map[oid] = order

        if record.get('oi_id') is not None:
            orders_map[oid]['items'].append({
                'id':            record['oi_id'],
                'product_id':    record['oi_product_id'],
                'product_name':  record['product_name'],
                'product_price': record['product_price'],
                'quantity':      record['oi_qty'],
                'unit':          record['oi_unit'],
            })

    return list(orders_map.values())


def update_order_status(order_id, status):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE orders SET order_status=%s WHERE id=%s", (status, order_id))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def count_orders(status=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        if status:
            cur.execute("SELECT COUNT(*) FROM orders WHERE order_status=%s", (status,))
        else:
            cur.execute("SELECT COUNT(*) FROM orders")
        n = cur.fetchone()[0]
        cur.close()
        return n
    finally:
        release_conn(conn)


def get_total_revenue():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE order_status != 'Cancelled'"
        )
        n = cur.fetchone()[0]
        cur.close()
        return float(n)
    finally:
        release_conn(conn)


def get_recent_orders(limit=10):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT o.*, u.username FROM orders o
            JOIN users u ON u.id = o.user_id
            ORDER BY o.created_at DESC LIMIT %s
        """, (limit,))
        rows = dictfetchall(cur)
        cur.close()
        return rows
    finally:
        release_conn(conn)


def get_revenue_chart_data(days=30):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT TO_CHAR(created_at::date, 'Mon DD') AS day,
                   COALESCE(SUM(total_amount), 0)      AS revenue
            FROM orders
            WHERE created_at >= NOW() - (INTERVAL '1 day' * %s)
              AND order_status != 'Cancelled'
            GROUP BY created_at::date, TO_CHAR(created_at::date, 'Mon DD')
            ORDER BY created_at::date
        """, (days,))
        rows = [{'day': r[0], 'revenue': float(r[1])} for r in cur.fetchall()]
        cur.close()
        return rows
    finally:
        release_conn(conn)


# ── Stock Logs ────────────────────────────────────────────────────────────────

def log_stock_change(product_id, admin_id, old_quantity, new_quantity, note=''):
    if old_quantity == new_quantity:
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO stock_logs (product_id, admin_id, old_quantity, new_quantity, note)
            VALUES (%s,%s,%s,%s,%s)
        """, (product_id, admin_id, old_quantity, new_quantity, note))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def get_stock_logs(product_id=None, limit=100):
    conn = get_conn()
    try:
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
        return rows
    finally:
        release_conn(conn)


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key=%s", (key,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
    finally:
        release_conn(conn)


def set_setting(key, value):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO settings (key, value) VALUES (%s,%s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (key, value))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def get_all_settings():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings")
        rows = {r[0]: r[1] for r in cur.fetchall()}
        cur.close()
        return rows
    finally:
        release_conn(conn)


# ── Audit Logs ────────────────────────────────────────────────────────────────
# ✅ FIXED: Admin action logging (Issue #12)

def log_admin_action(admin_id, action, entity_type, entity_id, details=None):
    """
    Log admin actions for audit trail.
    
    Examples:
    - log_admin_action(1, 'delete_product', 'product', 5, {'name': 'Tomato'})
    - log_admin_action(1, 'update_order_status', 'order', 12, {'old_status': 'Pending', 'new_status': 'Shipped'})
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        details_json = json.dumps(details or {})
        cur.execute("""
            INSERT INTO audit_logs (admin_id, action, entity_type, entity_id, details)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_id, action, entity_type, entity_id, details_json))
        conn.commit()
        cur.close()
    finally:
        release_conn(conn)


def get_audit_logs(limit=100):
    """Retrieve admin action logs."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT al.*, u.username FROM audit_logs al
            LEFT JOIN users u ON u.id = al.admin_id
            ORDER BY al.created_at DESC LIMIT %s
        """, (limit,))
        rows = dictfetchall(cur)
        cur.close()
        return rows
    finally:
        release_conn(conn)
