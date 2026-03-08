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
| Database  | PostgreSQL (via psycopg2) — Neon DB |
| Auth      | Flask sessions + Werkzeug hashing    |
| Frontend  | Jinja2 templates + custom CSS        |
| Uploads   | Werkzeug secure_filename + UUID     |

---

## 🚀 Setup & Run

### Prerequisites
- Python 3.10+
- pip
- PostgreSQL database (or Neon.tech free tier)

### Install & Start
```bash
# 1. Clone/cd into project
cd ammas_farm

# 2. Get a database URL from Neon.tech
# - Go to https://neon.tech (free tier available)
# - Create a new project and get your connection string
# - It looks like: postgresql://user:password@host/database

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export DATABASE_URL="postgresql://user:password@host/database"
export SECRET_KEY="your-secret-key-here"

# 5. Seed demo data (creates DB schema + demo users + 12 products)
python seed_data.py

# 6. Start the server
python app.py
```

✅ Open: **http://localhost:5000**

---

## 📊 Database Setup Details

This app uses **PostgreSQL** with **Neon.tech** (recommended for easy deployment):

### Local PostgreSQL Setup (Alternative)

If you want to run PostgreSQL locally instead of Neon:
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

### Neon.tech Setup (Recommended for Production)

1. Go to https://neon.tech
2. Sign up for free (includes $5 credit)
3. Create a new project
4. Copy the connection string (looks like `postgresql://...`)
5. Set: `export DATABASE_URL="your-connection-string"`
6. Run: `python seed_data.py`

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
- ✅ Secure file uploads with UUID naming
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
#   - DATABASE_URL: From Neon.tech
#   - FLASK_ENV: production

# 3. Deploy (auto-deploys on push to main)
```

### Environment Variables Required
```bash
DATABASE_URL=postgresql://user:password@host/database
SECRET_KEY=your-strong-secret-key-here
FLASK_ENV=production
```

### Image Upload to Cloud

For production, replace local file uploads with cloud storage:
```python
# Option 1: AWS S3
# Option 2: Cloudinary
# Option 3: Google Cloud Storage
```

Currently uses local `/static/uploads` — fine for development, not for production.

---

## 📝 License

Built with ❤️ for Amma's Farm 🌾