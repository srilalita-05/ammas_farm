# 🌾 Amma's Farm — Flask Web Application

A full-stack Flask e-commerce app for a local farmer to sell directly to customers.  
**No external ORM or auth library needed** — built with pure Flask + SQLite3 + Werkzeug.

---

## 🏗️ Project Structure

```
ammas_farm/
├── app.py              # Main Flask app — all routes
├── db.py               # All database helpers (sqlite3)
├── seed_data.py        # Demo data (admin + 12 products)
├── ammas_farm.db       # SQLite database (auto-created)
├── requirements.txt
├── static/
│   ├── css/style.css   # Full rural theme
│   └── uploads/        # Product images (auto-created)
└── templates/
    ├── base.html
    ├── auth/           login, register, profile
    ├── shop/           products, product_detail
    ├── cart/           cart
    ├── orders/         checkout, my_orders
    └── admin/          dashboard, products, product_form, orders
```

---

## ⚙️ Tech Stack

| Layer     | Technology                      |
|-----------|---------------------------------|
| Backend   | Flask 3.x                       |
| Database  | SQLite (via built-in sqlite3)   |
| Auth      | Flask sessions + Werkzeug hashing |
| Frontend  | Jinja2 templates + custom CSS   |
| Uploads   | Werkzeug secure_filename        |

---

## 🚀 Setup & Run

### Prerequisites
- Python 3.10+
- pip

### Install & Start

```bash
# 1. Install Flask (only dependency)
pip install flask

# 2. Seed demo data (creates DB + users + 12 products)
python seed_data.py

# 3. Start the server
python app.py
```

✅ Open: **http://localhost:5000**

---

## 🔐 Demo Login Credentials

| Role     | Username    | Password      |
|----------|-------------|---------------|
| Admin    | `admin`     | `admin123`    |
| Customer | `customer1` | `customer123` |

---

## 🗺️ URL Map

| URL                                   | Description                    | Access    |
|---------------------------------------|--------------------------------|-----------|
| `/shop`                               | Browse all products            | Public    |
| `/product/<id>`                       | Product detail page            | Public    |
| `/auth/register`                      | Register                       | Public    |
| `/auth/login`                         | Login                          | Public    |
| `/auth/logout`                        | Logout                         | User      |
| `/auth/profile`                       | Edit profile / change password | User      |
| `/cart`                               | View cart                      | Customer  |
| `/cart/add`                           | Add item to cart               | Customer  |
| `/cart/update/<id>`                   | Update cart item quantity      | Customer  |
| `/cart/remove/<id>`                   | Remove cart item               | Customer  |
| `/cart/clear`                         | Clear entire cart              | Customer  |
| `/checkout`                           | Place order                    | Customer  |
| `/my-orders`                          | Order history + status tracker | Customer  |
| `/admin/dashboard`                    | Stats, low stock, recent orders| Admin     |
| `/admin/products`                     | List / search products         | Admin     |
| `/admin/products/add`                 | Add new product                | Admin     |
| `/admin/products/<id>/edit`           | Edit product                   | Admin     |
| `/admin/products/<id>/delete`         | Delete product                 | Admin     |
| `/admin/orders`                       | All orders (filterable)        | Admin     |
| `/admin/orders/<id>/status`           | Update order status            | Admin     |

---

## 👤 User Roles

### Admin (Farmer)
- Full product management: add/edit/delete, image upload, stock, price, seasonal toggle
- View all customer orders, filter by status
- Update order status: **Pending → Packed → Shipped → Delivered**
- Dashboard with revenue stats, low-stock alerts, recent orders

### Customer
- Browse all products (no login needed)
- Register/login to buy
- Cart with live quantity management and stock validation
- Checkout with delivery address & phone
- Order history with visual progress tracker

---

## 🎨 UI Features

- 🌾 Earthy green & cream rural theme
- 📱 Mobile responsive grid layout
- 🔍 Search + filter (in-stock, seasonal, price sort)
- ⚠️ Low-stock badges and out-of-stock guards
- 🛒 Live cart badge counter in navbar
- 📊 4-step order progress tracker (Pending → Delivered)
- ✅ Flash messages with auto-dismiss

---

## 🔧 Production Notes

- Set `SECRET_KEY` via environment variable
- Replace SQLite with PostgreSQL (swap `db.py` connection string)
- Use S3/Cloudinary for image uploads
- Run behind gunicorn: `gunicorn app:app`
