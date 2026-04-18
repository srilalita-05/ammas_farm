import os
from werkzeug.security import generate_password_hash
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

new_password = 'bhuvana@123'
new_hash = generate_password_hash(new_password)

cur.execute(
    "UPDATE users SET password_hash = %s, role = 'admin' WHERE username = 'kavitha'",
    (new_hash,)
)

conn.commit()

cur.execute("SELECT username, email, role FROM users WHERE username = 'kavitha'")
print("Updated:", cur.fetchone())

cur.close()
conn.close()