# 🌾 Amma's Farm — Flask Web Application

A full-stack Flask e-commerce app for a local farmer to sell directly to customers.  
**No external ORM or auth library needed** — built with pure Flask + PostgreSQL + Werkzeug.

---

## 🏗️ Project Structure
```
ammas_farm/
├── app.py              # Main Flask app — all routes
├── db.py               # All database helpers (psycopg2)
├── seed_data.py        # Demo data (admin + 12 products)
├── requirements.txt
├── render.yaml         # Deployment configuration
├── static/
│   ├── css/style.css   # Full rural theme
│   └── uploads/        # Product images (auto-created)
└── templates/
    ├── base.html
    ├── auth/           login, register, profile
    ├── shop/           products, product_detail
    ├── cart/           cart
    ├── orders/         checkout, my_orders, confirmation
    └── admin/          dashboard, products, product_form, orders, categories, customers, settings, stock_logs, audit_log
```

---

## ⚙️ Tech Stack

| Layer     | Technology                           |
|-----------|--------------------------------------|
| Backend   | Flask 3.x                            |
| Database  | PostgreSQL (via psycopg2) — Aiven    |
| Auth      | Flask sessions + Werkzeug hashing    |
| Frontend  | Jinja2 templates + custom CSS        |
| Images    | Cloudinary CDN                       |

---

## 🚀 Setup & Run

### Prerequisites
- Python 3.10+
- pip
- PostgreSQL database (or Aiven free tier)

### Install & Start
```bash
# 1. Clone/cd into project
cd ammas_farm

# 2. Get a database URL from Aiven
# - Go to https://console.aiven.io (free tier available)
# - Create a new PostgreSQL service
# - Copy the Service URI from the connection details
# - It looks like: postgresql://user:password@host:port/database?sslmode=require

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export DATABASE_URL="postgresql://user:password@host:port/database?sslmode=require"
export SECRET_KEY="your-secret-key-here"

# 5. Seed demo data (creates DB schema + demo users + 12 products)
python seed_data.py

# 6. Start the server
python app.py
```

✅ Open: **http://localhost:5000**

---

## 📊 Database Setup Details

This app uses **PostgreSQL** hosted on **Aiven** (recommended — no inactivity pausing on the free tier, 5 GB storage).

### Aiven Setup (Recommended)

1. Go to https://console.aiven.io and create a free account
2. Create a new **PostgreSQL** service (free tier)
3. Once the service is running, go to the **Connection Information** tab
4. Copy the **Service URI** — it looks like `postgresql://avnadmin:password@host:port/defaultdb?sslmode=require`
5. Set: `export DATABASE_URL="your-service-uri"`
6. Run: `python seed_data.py`

> **Note:** The `?sslmode=require` at the end of the URI is required by Aiven. psycopg2 handles it automatically — no code changes needed.

### Local PostgreSQL Setup (Alternative)

```bash
# macOS with Homebrew
brew install postgresql
brew services start postgresql
createdb ammas_farm
export DATABASE_URL="postgresql://localhost/ammas_farm"

# Linux
sudo apt-get install postgresql postgresql-contrib
sudo -u postgres createdb ammas_farm
export DATABASE_URL="postgresql://postgres@localhost/ammas_farm"

# Then run seed_data.py
python seed_data.py
```

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
| `/admin/categories`                   | Manage product categories      | Admin     |
| `/admin/orders`                       | All orders (filterable)        | Admin     |
| `/admin/orders/<id>`                  | Order detail page              | Admin     |
| `/admin/orders/<id>/status`           | Update order status            | Admin     |
| `/admin/customers`                    | View all customers             | Admin     |
| `/admin/settings`                     | Email configuration (Resend)   | Admin     |
| `/admin/stock-logs`                   | Stock change history           | Admin     |
| `/admin/audit-log`                    | Admin actions audit trail      | Admin     |

---

## 👤 User Roles

### Admin (Farmer)
- Full product management: add/edit/delete, image upload, stock, price, seasonal toggle
- View all customer orders, filter by status
- Update order status: **Pending → Packed → Shipped → Delivered**
- Dashboard with revenue stats, low-stock alerts, recent orders
- View all customers and their purchase history
- Configure email notifications (Resend API)
- View audit log of all admin actions

### Customer
- Browse all products (no login needed)
- Register/login to buy
- Cart with live quantity management and stock validation
- Checkout with delivery address & phone
- Order history with visual progress tracker
- Update profile and delivery address
- Change password

---

## 🎨 UI Features

- 🌾 Earthy green & cream rural theme
- 📱 Mobile responsive grid layout
- 🔍 Search + filter (in-stock, seasonal, price sort)
- ⚠️ Low-stock badges and out-of-stock guards
- 🛒 Live cart badge counter in navbar
- 📊 4-step order progress tracker (Pending → Delivered)
- ✅ Flash messages with auto-dismiss
- 🎬 Full-page farm canvas animation (wheat, flowers, petals, pollen)

---

## 🔐 Security Features

- ✅ CSRF protection on all POST routes
- ✅ Password hashing with Werkzeug
- ✅ Parameterized SQL queries (no injection)
- ✅ Email domain whitelist (prevents spam signups)
- ✅ Session-based authentication
- ✅ Secure image uploads via Cloudinary
- ✅ Stock validation at checkout (prevents overselling)
- ✅ Audit logging of all admin actions

---

## 🐛 Bug Fixes & Issues Resolved

This version includes fixes for critical issues:

1. ✅ **Deleted product crashes checkout** — Now validates product exists before checkout
2. ✅ **Race condition in order creation** — Try-catch with proper error handling
3. ✅ **Duplicate user registration** — Catches IntegrityError at database level
4. ✅ **Silent email failures** — Shows warning if email doesn't send
5. ✅ **Email validation on profile** — Validates email domain when updating profile
6. ✅ **Deleted products in cart** — Shows warning for unavailable items
7. ✅ **Image file deletion errors** — Graceful handling of file system errors
8. ✅ **Missing seasonal check** — Validates seasonal availability at checkout
9. ✅ **Admin action logging** — Complete audit trail of all admin actions

---

## 🔧 Production Deployment

### Render.com (Recommended)
```bash
# 1. Push code to GitHub
git push origin main

# 2. Create new Web Service on Render
# - Connect your GitHub repo
# - Set environment variables:
#   - SECRET_KEY: Generate strong random key
#   - DATABASE_URL: Service URI from Aiven (includes ?sslmode=require)
#   - FLASK_ENV: production
#   - CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

# 3. Deploy (auto-deploys on push to main)
```

### Environment Variables Required
```bash
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
SECRET_KEY=your-strong-secret-key-here
FLASK_ENV=production
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

---

## 📝 License

Built with ❤️ for Amma's Farm 🌾
