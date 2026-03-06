import db as database


def seed():
    # Ensure tables exist first
    database.init_db()

    conn = database.get_conn()
    cur = conn.cursor()

    # Example products
    products = [
        ("Tomatoes", "Fresh farm tomatoes", 40, 100, "kg"),
        ("Potatoes", "Organic potatoes", 30, 150, "kg"),
        ("Milk", "Fresh cow milk", 60, 50, "litre"),
        ("Eggs", "Country eggs", 8, 200, "piece"),
    ]

    for name, desc, price, stock, unit in products:
        cur.execute(
            """
            INSERT INTO products (name, description, price, stock_quantity, unit)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, desc, price, stock, unit)
        )

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Sample data inserted successfully!")


if __name__ == "__main__":
    seed()