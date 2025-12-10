import sqlite3

conn = sqlite3.connect("whatsut.db")
cursor = conn.cursor()

cursor.execute("SELECT id, username, banned FROM users")
for row in cursor.fetchall():
    print(row)
