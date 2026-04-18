"""seed_data.py — Populate Amma's Farm with demo data."""

import db as database


def seed():
    database.init_db()
    conn = database.get_conn()
    cur = conn.cursor()

    # ── 1. Admin user ─────────────────────────────────────────────────────────
    cur.execute("SELECT id FROM users WHERE username='admin'")
    if not cur.fetchone():
        database.create_user('kavitha', 'admin@ammasfarm.com', 'bhuvana@123', role='admin')
        print("✅ Admin user created  (kavitha / bhuvana@123)")
    else:
        print("ℹ️  Admin user already exists")

    # ── 2. Demo customer ──────────────────────────────────────────────────────
    cur.execute("SELECT id FROM users WHERE username='customer1'")
    if not cur.fetchone():
        database.create_user('customer1', 'customer1@example.com', 'customer123', role='customer')
        print("✅ Demo customer created  (customer1 / customer123)")
    else:
        print("ℹ️  Demo customer already exists")

    # ── 3. Categories ─────────────────────────────────────────────────────────
    categories = [
        ('Vegetables',  '🥦'),
        ('Fruits',      '🍎'),
        ('Dairy',       '🥛'),
        ('Grains',      '🌾'),
        ('Herbs',       '🌿'),
        ('Eggs',        '🥚'),
    ]
    cat_ids = {}
    for name, icon in categories:
        cur.execute("SELECT id FROM categories WHERE name=%s", (name,))
        row = cur.fetchone()
        if row:
            cat_ids[name] = row[0]
        else:
            cur.execute(
                "INSERT INTO categories (name, icon) VALUES (%s,%s) RETURNING id",
                (name, icon)
            )
            cat_ids[name] = cur.fetchone()[0]
    conn.commit()
    print(f"✅ {len(categories)} categories seeded")

    # ── 4. Products ───────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] > 0:
        print("ℹ️  Products already exist — skipping product seed")
        cur.close()
        conn.close()
        return

    products = [
        # name, description, price, stock, unit, threshold, seasonal, category
        ("Fresh Tomatoes",
         "Juicy, sun-ripened tomatoes straight from the vine. Perfect for salads and curries.",
         40, 120, 'kg', 15, 1, 'Vegetables'),

        ("Organic Potatoes",
         "Earthy, floury potatoes grown without pesticides. Great for sabzi or fries.",
         30, 200, 'kg', 20, 1, 'Vegetables'),

        ("Green Spinach",
         "Tender baby spinach, hand-picked at peak freshness. Rich in iron.",
         25, 80, 'bundle', 10, 1, 'Vegetables'),

        ("Alphonso Mangoes",
         "The king of mangoes — sweet, fiberless, and intensely aromatic.",
         220, 50, 'dozen', 8, 1, 'Fruits'),

        ("Banana (Nendran)",
         "Thick, sweet Nendran bananas. Ideal for eating fresh or making chips.",
         60, 90, 'dozen', 12, 1, 'Fruits'),

        ("Guava",
         "Crisp, pink-fleshed guavas loaded with Vitamin C.",
         55, 70, 'kg', 10, 1, 'Fruits'),

        ("Fresh Cow Milk",
         "Farm-fresh A2 cow milk, collected every morning. No preservatives.",
         70, 60, 'litre', 8, 1, 'Dairy'),

        ("Homemade Ghee",
         "Slow-churned, golden ghee made from cultured cream. Rich nutty aroma.",
         650, 30, 'kg', 5, 1, 'Dairy'),

        ("Country Eggs",
         "Free-range country eggs from desi hens. Rich orange yolks, full of nutrition.",
         8, 300, 'piece', 30, 1, 'Eggs'),

        ("Brown Rice",
         "Hand-pounded brown rice. Retains bran layer for maximum fibre and nutrients.",
         90, 150, 'kg', 20, 1, 'Grains'),

        ("Curry Leaves",
         "Fresh, fragrant curry leaves bunches, cut daily from our grove.",
         10, 100, 'bundle', 15, 1, 'Herbs'),

        ("Drumstick (Moringa)",
         "Long, tender drumstick pods — a staple of South Indian cooking.",
         35, 60, 'bundle', 8, 1, 'Vegetables'),
    ]

    for (name, desc, price, stock, unit, threshold, seasonal, cat_name) in products:
        pid = database.create_product(
            name=name,
            description=desc,
            price=price,
            stock_quantity=stock,
            unit=unit,
            low_stock_threshold=threshold,
            seasonal_availability=seasonal,
            category_id=cat_ids.get(cat_name),
            image=''
        )
        # Log initial stock
        admin = database.get_user_by_username('admin')
        if admin:
            database.log_stock_change(pid, admin['id'], 0, stock, 'Initial stock from seed')

    cur.close()
    conn.close()
    print(f"✅ {len(products)} products seeded")
    print("\n🌾 Seed complete!")
    print("   Admin login:    admin / admin123")
    print("   Customer login: customer1 / customer123")
    print("   URL:            http://localhost:5000")


if __name__ == "__main__":
    seed()