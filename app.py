"""app.py — Amma's Farm Flask application."""

import os, time, secrets, json
import urllib.request, urllib.error
from functools import wraps
from flask import (Flask, render_template, redirect, url_for, flash,
                   request, session, g, jsonify, abort)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import cloudinary
import cloudinary.uploader
import db as database
from dotenv import load_dotenv
load_dotenv()

BASE_DIR      = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXT   = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ammas-farm-dev-secret-change-me')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
database.init_db()

# ── Cloudinary config ─────────────────────────────────────────────────────────

cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key    = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
)

# ── Allowed email domains ────────────────────────────────────────────

ALLOWED_EMAIL_DOMAINS = {
    'gmail.com', 'googlemail.com',
    'outlook.com', 'hotmail.com', 'hotmail.in', 'hotmail.co.uk',
    'live.com', 'live.in', 'live.co.uk', 'msn.com', 'windowslive.com',
    'yahoo.com', 'yahoo.in', 'yahoo.co.in', 'yahoo.co.uk', 'yahoo.com.au',
    'ymail.com', 'rocketmail.com',
    'icloud.com', 'me.com', 'mac.com',
    'protonmail.com', 'proton.me',
    'zoho.com', 'zohomail.com',
    'aol.com', 'aim.com',
    'rediffmail.com', 'indiatimes.com', 'sify.com', 'vsnl.com',
    'tutanota.com', 'tuta.com',
    'fastmail.com', 'fastmail.fm',
    'gmx.com', 'gmx.net', 'gmx.de',
    'web.de', 'mail.com', 'inbox.com',
    'mail.ru', 'yandex.com', 'yandex.ru',
    'comcast.net', 'verizon.net', 'att.net', 'cox.net', 'sbcglobal.net',
}

def is_allowed_email(email: str) -> bool:
    parts = email.strip().lower().split('@')
    return len(parts) == 2 and parts[1] in ALLOWED_EMAIL_DOMAINS

def build_address(form) -> str:
    """Combine individual address fields into one readable string."""
    house   = form.get('house_no', '').strip()
    street  = form.get('street', '').strip()
    city    = form.get('city', '').strip()
    state   = form.get('state', '').strip()
    pincode = form.get('pincode', '').strip()
    parts = [p for p in [house, street, city, state] if p]
    address = ', '.join(parts)
    if pincode:
        address += f' - {pincode}'
    return address


# ── CSRF ──────────────────────────────────────────────────────────────────────

def get_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf():
    token = request.form.get('csrf_token', '')
    return token and token == session.get('csrf_token', '')

@app.before_request
def csrf_protect():
    if request.method == 'POST':
        if request.path.startswith('/admin/api/'):
            return
        if not validate_csrf():
            flash('Security token mismatch. Please try again.', 'error')
            return redirect(request.referrer or url_for('shop'))

app.jinja_env.globals['csrf_token'] = get_csrf_token

# ── 413 handler — oversized image upload ─────────────────────────────────────

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash('Image is too large. Please upload a file smaller than 5MB.', 'error')
    return redirect(request.referrer or url_for('admin_products')), 413

# ── Auth helpers ──────────────────────────────────────────────────────────────

def login_user(user):
    session['user_id'] = user['id']

def logout_user():
    session.pop('user_id', None)

# ── Single before_request: loads user + cart count + categories ──────────────

@app.before_request
def load_user():
    g.user       = None
    g.cart_count = 0
    g.categories = []

    conn = database.get_conn()
    try:
        cur = conn.cursor()

        if 'user_id' in session:
            cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
            g.user = database.dictfetchone(cur)

        if g.user:
            cur.execute(
                "SELECT COALESCE(SUM(quantity),0) FROM cart_items WHERE user_id=%s",
                (g.user['id'],)
            )
            g.cart_count = int(cur.fetchone()[0])

        now = time.time()
        if not hasattr(app, '_cat_cache') or now - app._cat_cache_time > 300:
            cur.execute("SELECT * FROM categories ORDER BY name")
            app._cat_cache      = database.dictfetchall(cur)
            app._cat_cache_time = now
        g.categories = app._cat_cache

        cur.close()
    finally:
        database.release_conn(conn)

@app.context_processor
def inject_globals():
    return dict(
        current_user   = g.user,
        cart_count     = g.cart_count,
        all_categories = g.categories,
    )

def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if not g.user:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('login', next=request.url))
        return f(*a, **kw)
    return dec

def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if not g.user or g.user['role'] != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

# ── Template helpers ──────────────────────────────────────────────────────────

def full_name(user):
    n = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
    return n or user['username']

def product_is_available(p):
    return p['stock_quantity'] > 0

def product_is_low_stock(p):
    return 0 < p['stock_quantity'] <= p['low_stock_threshold']

def status_index(order):
    try: return ['Pending','Packed','Shipped','Delivered'].index(order['order_status'])
    except ValueError: return 0

def item_subtotal(item):       return item['price'] * item['quantity']
def order_item_subtotal(item): return item['product_price'] * item['quantity']

app.jinja_env.globals.update(
    full_name=full_name,
    product_is_available=product_is_available,
    product_is_low_stock=product_is_low_stock,
    status_index=status_index,
    item_subtotal=item_subtotal,
    order_item_subtotal=order_item_subtotal,
    ORDER_STATUSES=['Pending','Packed','Shipped','Delivered'],
)

# ── File uploads ──────────────────────────────────────────────────────────────

def allowed_file(fn): return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED_EXT

def save_upload(file_obj):
    """Upload to Cloudinary and return the secure URL, or None on failure."""
    if not file_obj or not file_obj.filename:
        return None
    if not allowed_file(file_obj.filename):
        flash('Invalid file type. Please upload a PNG, JPG, GIF, or WEBP image.', 'error')
        return None
    try:
        result = cloudinary.uploader.upload(
            file_obj,
            folder="ammas_farm",
            transformation=[{"width": 600, "crop": "limit"}]
        )
        return result['secure_url']
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        flash('Image upload failed. The product was saved without an image.', 'warning')
        return None

def delete_image(image_val):
    """Delete image only if it's a local file (not a Cloudinary URL)."""
    if image_val and not image_val.startswith('http'):
        old_path = os.path.join(UPLOAD_FOLDER, image_val)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception as e:
                print(f"Image deletion error: {e}")

# ── Email via Resend ──────────────────────────────────────────────────────────

def send_resend_email(to, subject, html_body):
    api_key    = database.get_setting('resend_api_key')
    from_email = database.get_setting('resend_from_email')
    enabled    = database.get_setting('email_notifications') == '1'
    if not enabled or not api_key or not to:
        return False, 'Email notifications disabled or not configured'
    payload = json.dumps({
        'from': from_email,
        'to': [to],
        'subject': subject,
        'html': html_body,
    }).encode()
    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=payload,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()}"
    except Exception as e:
        return False, str(e)

def notify_order_placed(order, user):
    items_html = ''.join(
        f"<tr><td style='padding:6px 12px'>{i['product_name']}</td>"
        f"<td style='padding:6px 12px'>{i['quantity']} {i['unit']}</td>"
        f"<td style='padding:6px 12px'>₹{i['product_price']*i['quantity']:.2f}</td></tr>"
        for i in order['items']
    )
    customer_html = f"""
    <div style='font-family:sans-serif;max-width:580px;margin:auto;background:#fdf6e3;border-radius:12px;padding:32px;border:1px solid #d4c9a8'>
      <h2 style='color:#2d5016;margin-top:0'>🌾 Order Confirmed! Order #{order['id']}</h2>
      <p style='color:#6b7280'>Hi {full_name(user)}, your order has been placed successfully.</p>
      <table style='width:100%;border-collapse:collapse;margin:16px 0;background:#fff;border-radius:8px;overflow:hidden;border:1px solid #d4c9a8'>
        <thead><tr style='background:#2d5016;color:#fff'>
          <th style='padding:8px 12px;text-align:left'>Product</th>
          <th style='padding:8px 12px;text-align:left'>Qty</th>
          <th style='padding:8px 12px;text-align:left'>Amount</th>
        </tr></thead>
        <tbody>{items_html}</tbody>
        <tfoot><tr style='background:#e8f5d8'>
          <td colspan='2' style='padding:8px 12px;font-weight:bold'>Total</td>
          <td style='padding:8px 12px;font-weight:bold'>₹{order['total_amount']:.2f}</td>
        </tr></tfoot>
      </table>
      <p style='color:#6b7280'><strong>Delivering to:</strong> {order['delivery_address']}</p>
      <p style='color:#6b7280'><strong>Contact:</strong> {order['phone_number']}</p>
      <p style='color:#2d5016;font-weight:bold'>We'll update you as your order progresses. Thank you! 🌱</p>
    </div>"""
    send_resend_email(user['email'], f"Order #{order['id']} Confirmed — Amma's Farm 🌾", customer_html)

    admin_email = database.get_setting('resend_admin_email')
    if admin_email:
        admin_html = f"""
        <div style='font-family:sans-serif;max-width:580px;margin:auto'>
          <h2 style='color:#2d5016'>🛒 New Order #{order['id']}</h2>
          <p><strong>Customer:</strong> {full_name(user)} ({user['email']})</p>
          <p><strong>Amount:</strong> ₹{order['total_amount']:.2f}</p>
          <p><strong>Delivery:</strong> {order['delivery_address']}</p>
          <table style='width:100%;border-collapse:collapse;margin:12px 0'>
            <thead><tr style='background:#2d5016;color:#fff'>
              <th style='padding:6px 10px;text-align:left'>Product</th>
              <th style='padding:6px 10px'>Qty</th>
              <th style='padding:6px 10px'>Amount</th>
            </tr></thead>
            <tbody>{items_html}</tbody>
          </table>
        </div>"""
        send_resend_email(admin_email, f"New Order #{order['id']} — ₹{order['total_amount']:.2f}", admin_html)

# ── Root ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index(): return redirect(url_for('shop'))

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/auth/register', methods=['GET','POST'])
def register():
    if g.user: return redirect(url_for('shop'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email    = request.form.get('email','').strip()
        password = request.form.get('password','')
        confirm  = request.form.get('confirm_password','')
        if not username or not email or not password:
            flash('All fields are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif not is_allowed_email(email):
            flash('Please use a recognised email provider (Gmail, Outlook, Yahoo, etc.).', 'error')
        elif database.get_user_by_username(username):
            flash('Username already taken.', 'error')
        elif database.get_user_by_email(email):
            flash('Email already registered.', 'error')
        else:
            database.create_user(username, email, password)
            login_user(database.get_user_by_username(username))
            flash("Welcome to Amma's Farm! 🌾", 'success')
            return redirect(url_for('shop'))
    return render_template('auth/register.html')

@app.route('/auth/login', methods=['GET','POST'])
def login():
    if g.user: return redirect(url_for('shop'))
    if request.method == 'POST':
        user = database.get_user_by_username(request.form.get('username','').strip())
        if user and database.verify_password(user, request.form.get('password','')):
            login_user(user)
            flash(f"Welcome back, {full_name(user)}! 🌾", 'success')
            next_page = request.args.get('next')
            return redirect(next_page or (url_for('admin_dashboard') if user['role']=='admin' else url_for('shop')))
        flash('Invalid username or password.', 'error')
    return render_template('auth/login.html')

@app.route('/auth/logout')
def logout():
    logout_user(); flash('You have been logged out.', 'info')
    return redirect(url_for('shop'))

@app.route('/auth/profile', methods=['GET','POST'])
@login_required
def profile():
    if request.method == 'POST':
        updates = {k: request.form.get(k,'').strip() for k in
                   ['first_name','last_name','email','phone_number']}
        updates['address'] = build_address(request.form)
        new_pw = request.form.get('new_password','')
        if new_pw:
            if not database.verify_password(g.user, request.form.get('current_password','')):
                flash('Current password is incorrect.', 'error')
                return render_template('auth/profile.html')
            updates['password'] = new_pw
        database.update_user(g.user['id'], **updates)
        g.user = database.get_user_by_id(g.user['id'])
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('auth/profile.html')

# ── Shop ──────────────────────────────────────────────────────────────────────

@app.route('/shop')
def shop():
    q           = request.args.get('search','').strip()
    available   = request.args.get('available_only') == 'true'
    seasonal    = request.args.get('seasonal') == 'true'
    ordering    = request.args.get('ordering','name')
    page        = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    per_page    = 12
    items, total = database.get_products(
        search=q, available_only=available, seasonal=seasonal,
        ordering=ordering, category_id=category_id, page=page, per_page=per_page)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template('shop/products.html',
                           products=items, total=total,
                           page=page, total_pages=total_pages,
                           query=q, available_only=available,
                           seasonal=seasonal, ordering=ordering,
                           active_category=category_id)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = database.get_product(product_id)
    if not product: flash('Product not found.','error'); return redirect(url_for('shop'))
    return render_template('shop/product_detail.html', product=product)

# ── Cart ──────────────────────────────────────────────────────────────────────

@app.route('/cart')
@login_required
def view_cart():
    items = database.get_cart_items(g.user['id'])
    return render_template('cart/cart.html', items=items, total=sum(item_subtotal(i) for i in items))

@app.route('/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    product_id = request.form.get('product_id', type=int)
    quantity   = request.form.get('quantity', 1, type=int)
    next_url   = request.form.get('next') or url_for('shop')
    if not product_id or quantity < 1:
        flash('Invalid.', 'error'); return redirect(next_url)
    product = database.get_product(product_id)
    if not product or not product_is_available(product):
        flash(f"{'Product not found' if not product else product['name']+' is unavailable'}.", 'error')
        return redirect(next_url)
    existing = database.get_cart_item_by_product(g.user['id'], product_id)
    new_qty  = (existing['quantity'] if existing else 0) + quantity
    if new_qty > product['stock_quantity']:
        flash(f"Only {product['stock_quantity']} {product['unit']} available.", 'error')
        return redirect(next_url)
    database.add_or_update_cart(g.user['id'], product_id, quantity)
    flash(f"{product['name']} added to cart! 🛒", 'success')
    return redirect(next_url)

@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart_item(item_id):
    item    = database.get_cart_item(item_id, g.user['id'])
    if not item: return redirect(url_for('view_cart'))
    quantity = request.form.get('quantity', type=int)
    product  = database.get_product(item['product_id'])
    if not quantity or quantity < 1:
        database.delete_cart_item(item_id); flash('Item removed.', 'info')
    elif quantity > product['stock_quantity']:
        flash(f"Only {product['stock_quantity']} {product['unit']} available.", 'error')
    else:
        database.update_cart_item_qty(item_id, quantity); flash('Cart updated.', 'success')
    return redirect(url_for('view_cart'))

@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_cart_item(item_id):
    database.delete_cart_item(item_id); flash('Item removed.', 'info')
    return redirect(url_for('view_cart'))

@app.route('/cart/clear', methods=['POST'])
@login_required
def clear_cart():
    database.clear_cart(g.user['id']); flash('Cart cleared.', 'info')
    return redirect(url_for('view_cart'))

# ── Orders ────────────────────────────────────────────────────────────────────

@app.route('/checkout', methods=['GET','POST'])
@login_required
def checkout():
    items = database.get_cart_items(g.user['id'])
    if not items: flash('Your cart is empty.','info'); return redirect(url_for('view_cart'))
    total = sum(item_subtotal(i) for i in items)
    if request.method == 'POST':
        delivery_address = build_address(request.form)
        phone_number     = request.form.get('phone_number','').strip()
        notes            = request.form.get('notes','').strip()
        if not delivery_address or not phone_number:
            flash('Delivery address and phone number are required.','error')
            return render_template('orders/checkout.html', items=items, total=total)
        for item in items:
            p = database.get_product(item['product_id'])
            if item['quantity'] > p['stock_quantity']:
                flash(f"Insufficient stock for {item['name']}.","error")
                return render_template('orders/checkout.html', items=items, total=total)
        order_id = database.create_order(g.user['id'], total, delivery_address, phone_number, notes, items)
        order = database.get_order_full(order_id)
        try: notify_order_placed(order, g.user)
        except Exception: pass
        flash(f'Order #{order_id} placed successfully! 🎉','success')
        return redirect(url_for('order_confirmation', order_id=order_id))
    return render_template('orders/checkout.html', items=items, total=total)

@app.route('/orders/<int:order_id>/confirmation')
@login_required
def order_confirmation(order_id):
    order = database.get_order_full(order_id)
    if not order or order['user_id'] != g.user['id']:
        flash('Order not found.','error'); return redirect(url_for('my_orders'))
    return render_template('orders/confirmation.html', order=order)

@app.route('/my-orders')
@login_required
def my_orders():
    search        = request.args.get('search','').strip()
    status_filter = request.args.get('status','')
    orders = database.get_my_orders(g.user['id'], search=search, status_filter=status_filter)
    return render_template('orders/my_orders.html', orders=orders,
                           search=search, status_filter=status_filter)

# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    stats = {
        'total_products':  database.count_products(),
        'total_orders':    database.count_orders(),
        'total_customers': database.count_customers(),
        'total_revenue':   database.get_total_revenue(),
        'pending_orders':  database.count_orders('Pending'),
        'out_of_stock':    database.count_out_of_stock(),
    }
    return render_template('admin/dashboard.html',
                           stats=stats,
                           low_stock_products=database.get_low_stock_products(),
                           recent_orders=database.get_recent_orders())

@app.route('/admin/api/revenue-chart')
@login_required
@admin_required
def admin_revenue_chart():
    days = request.args.get('days', 30, type=int)
    data = database.get_revenue_chart_data(days)
    return jsonify(data)

@app.route('/admin/products')
@login_required
@admin_required
def admin_products():
    q   = request.args.get('search','').strip()
    cat = request.args.get('category', type=int)
    return render_template('admin/products.html',
                           products=database.get_all_products(search=q, category_id=cat),
                           query=q, active_category=cat)

@app.route('/admin/products/add', methods=['GET','POST'])
@login_required
@admin_required
def admin_add_product():
    categories = database.get_all_categories()
    if request.method == 'POST':
        name      = request.form.get('name','').strip()
        desc      = request.form.get('description','').strip()
        price     = request.form.get('price', type=float)
        stock     = request.form.get('stock_quantity', type=int)
        unit      = request.form.get('unit','kg').strip()
        threshold = request.form.get('low_stock_threshold', 10, type=int)
        seasonal  = 1 if request.form.get('seasonal_availability') == 'on' else 0
        cat_id    = request.form.get('category_id', type=int) or None
        note      = request.form.get('stock_note','').strip()
        if not name or price is None or stock is None:
            flash('Name, price, and stock are required.','error')
            return render_template('admin/product_form.html', product=None, categories=categories)
        img = save_upload(request.files.get('image')) or ''
        pid = database.create_product(name=name, description=desc, price=price,
                                      stock_quantity=stock, unit=unit,
                                      low_stock_threshold=threshold,
                                      seasonal_availability=seasonal,
                                      category_id=cat_id, image=img)
        database.log_stock_change(pid, g.user['id'], 0, stock, note or 'Initial stock')
        database.log_admin_action(
            g.user['id'], 'add_product', 'product', pid,
            {'name': name, 'price': price, 'stock': stock}
        )
        if hasattr(app, '_cat_cache'):
            app._cat_cache_time = 0
        flash(f'Product "{name}" added! 🌱','success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', product=None, categories=categories)

@app.route('/admin/products/<int:product_id>/edit', methods=['GET','POST'])
@login_required
@admin_required
def admin_edit_product(product_id):
    product    = database.get_product(product_id)
    categories = database.get_all_categories()
    stock_logs = database.get_stock_logs(product_id, limit=10)
    if not product: flash('Product not found.','error'); return redirect(url_for('admin_products'))
    if request.method == 'POST':
        old_stock = product['stock_quantity']
        old_price = product['price']
        new_stock = request.form.get('stock_quantity', type=int)
        new_price = request.form.get('price', type=float)
        note      = request.form.get('stock_note','').strip()
        updates = {
            'name':                request.form.get('name','').strip(),
            'description':         request.form.get('description','').strip(),
            'price':               new_price,
            'stock_quantity':      new_stock,
            'unit':                request.form.get('unit','kg').strip(),
            'low_stock_threshold': request.form.get('low_stock_threshold', 10, type=int),
            'seasonal_availability': 1 if request.form.get('seasonal_availability')=='on' else 0,
            'category_id':         request.form.get('category_id', type=int) or None,
        }
        new_img = save_upload(request.files.get('image'))
        if new_img:
            delete_image(product['image'])
            updates['image'] = new_img
        database.update_product(product_id, **updates)
        if new_stock is not None:
            database.log_stock_change(product_id, g.user['id'], old_stock, new_stock, note)
        changed = {}
        if updates['name'] != product['name']:
            changed['name'] = {'old': product['name'], 'new': updates['name']}
        if new_price is not None and new_price != old_price:
            changed['price'] = {'old': old_price, 'new': new_price}
        if new_stock is not None and new_stock != old_stock:
            changed['stock'] = {'old': old_stock, 'new': new_stock}
        database.log_admin_action(
            g.user['id'], 'edit_product', 'product', product_id,
            changed or {'name': updates['name']}
        )
        flash('Product updated!','success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', product=product,
                           categories=categories, stock_logs=stock_logs)

@app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_product(product_id):
    product = database.get_product(product_id)
    if product:
        delete_image(product['image'])
        database.delete_product(product_id)
        database.log_admin_action(
            g.user['id'], 'delete_product', 'product', product_id,
            {'name': product['name']}
        )
        flash(f"Product \"{product['name']}\" deleted.",'info')
    return redirect(url_for('admin_products'))

@app.route('/admin/categories', methods=['GET','POST'])
@login_required
@admin_required
def admin_categories():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name','').strip()
            icon = request.form.get('icon','🌿').strip()
            if name:
                database.create_category(name, icon)
                if hasattr(app, '_cat_cache'):
                    app._cat_cache_time = 0
                database.log_admin_action(
                    g.user['id'], 'add_category', 'category', None,
                    {'name': name, 'icon': icon}
                )
                flash(f'Category "{name}" added!','success')
            else:
                flash('Category name required.','error')
        elif action == 'delete':
            cat_id = request.form.get('cat_id', type=int)
            if cat_id:
                database.delete_category(cat_id)
                if hasattr(app, '_cat_cache'):
                    app._cat_cache_time = 0
                database.log_admin_action(
                    g.user['id'], 'delete_category', 'category', cat_id, {}
                )
                flash('Category deleted.','info')
        return redirect(url_for('admin_categories'))
    return render_template('admin/categories.html', categories=database.get_all_categories())

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    status_filter = request.args.get('status','')
    search        = request.args.get('search','').strip()
    orders = database.get_all_orders(status_filter=status_filter, search=search)
    return render_template('admin/orders.html', orders=orders,
                           status_filter=status_filter, search=search)

@app.route('/admin/orders/<int:order_id>')
@login_required
@admin_required
def admin_order_detail(order_id):
    order = database.get_order_full(order_id)
    if not order: flash('Order not found.','error'); return redirect(url_for('admin_orders'))
    return render_template('admin/order_detail.html', order=order)

@app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
@login_required
@admin_required
def admin_update_order_status(order_id):
    new_status = request.form.get('status')
    if new_status not in ['Pending','Packed','Shipped','Delivered']:
        flash('Invalid status.','error')
    else:
        order = database.get_order_full(order_id)
        old_status = order['order_status'] if order else '?'
        database.update_order_status(order_id, new_status)
        database.log_admin_action(
            g.user['id'], 'update_order_status', 'order', order_id,
            {'old_status': old_status, 'new_status': new_status}
        )
        flash(f'Order #{order_id} updated to {new_status}.','success')
    return redirect(request.referrer or url_for('admin_orders'))

@app.route('/admin/customers')
@login_required
@admin_required
def admin_customers():
    search    = request.args.get('search','').strip()
    customers = database.get_all_customers(search=search)
    return render_template('admin/customers.html', customers=customers, search=search)

@app.route('/admin/settings', methods=['GET','POST'])
@login_required
@admin_required
def admin_settings():
    if request.method == 'POST':
        keys = ['resend_api_key','resend_from_email','resend_admin_email','email_notifications']
        for key in keys:
            val = request.form.get(key, '').strip()
            if key == 'email_notifications':
                val = '1' if request.form.get('email_notifications') == 'on' else '0'
            database.set_setting(key, val)
        if request.form.get('test_email'):
            admin_email = database.get_setting('resend_admin_email')
            ok, msg = send_resend_email(
                admin_email,
                "Test Email — Amma's Farm 🌾",
                "<h2 style='color:#2d5016'>✅ Email is working!</h2><p>Your Resend configuration is set up correctly on Amma's Farm.</p>"
            )
            flash(f"Test email {'sent successfully ✅' if ok else 'failed ❌: ' + str(msg)}", 'success' if ok else 'error')
        else:
            flash('Settings saved!','success')
        return redirect(url_for('admin_settings'))
    return render_template('admin/settings.html', settings=database.get_all_settings())

@app.route('/admin/stock-logs')
@login_required
@admin_required
def admin_stock_logs():
    logs = database.get_stock_logs(limit=100)
    return render_template('admin/stock_logs.html', logs=logs)

@app.route('/admin/audit-log')
@login_required
@admin_required
def admin_audit_log():
    logs = database.get_audit_logs(limit=100)
    return render_template('admin/audit_log.html', logs=logs)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form_success = False
    form_data = None
    if request.method == 'POST':
        form_data = {
            'name':    request.form.get('name', '').strip(),
            'phone':   request.form.get('phone', '').strip(),
            'email':   request.form.get('email', '').strip(),
            'subject': request.form.get('subject', '').strip(),
            'message': request.form.get('message', '').strip(),
        }
        if form_data['name'] and form_data['email'] and form_data['subject'] and form_data['message']:
            admin_email = database.get_setting('resend_admin_email')
            if admin_email:
                html_body = f"""
                <div style='font-family:sans-serif;max-width:580px;margin:auto;background:#fdf6e3;
                            border-radius:12px;padding:32px;border:1px solid #d4c9a8'>
                  <h2 style='color:#2d5016;margin-top:0'>📬 New Contact Form Message</h2>
                  <table style='width:100%;border-collapse:collapse;font-size:0.9rem'>
                    <tr><td style='padding:6px 0;color:#6b7280;width:100px'><strong>Name</strong></td>
                        <td style='padding:6px 0'>{form_data['name']}</td></tr>
                    <tr><td style='padding:6px 0;color:#6b7280'><strong>Email</strong></td>
                        <td style='padding:6px 0'>{form_data['email']}</td></tr>
                    <tr><td style='padding:6px 0;color:#6b7280'><strong>Phone</strong></td>
                        <td style='padding:6px 0'>{form_data['phone'] or '—'}</td></tr>
                    <tr><td style='padding:6px 0;color:#6b7280'><strong>Subject</strong></td>
                        <td style='padding:6px 0'>{form_data['subject']}</td></tr>
                  </table>
                  <div style='margin-top:1rem;padding:1rem;background:#fff;border-radius:8px;
                              border:1px solid #d4c9a8;font-size:0.9rem;line-height:1.6'>
                    {form_data['message']}
                  </div>
                  <p style='color:#6b7280;font-size:0.82rem;margin-top:1rem'>
                    Sent via the Contact Us form on Amma's Farm
                  </p>
                </div>"""
                send_resend_email(
                    admin_email,
                    f"Contact Form: {form_data['subject']} — {form_data['name']}",
                    html_body
                )
            form_success = True
            form_data = None
        else:
            flash('Please fill in all required fields.', 'error')
    return render_template('contact.html', form_success=form_success, form_data=form_data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)