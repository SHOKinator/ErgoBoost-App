import sqlite3
c = sqlite3.connect('data/ergoboost.db')
rows = c.execute('SELECT id, username, display_name, created_at FROM users').fetchall()
print("=== Users in database ===")
for r in rows:
    print(f"  ID: {r[0]}, Username: {r[1]}, Display: {r[2]}, Created: {r[3]}")
sessions = c.execute('SELECT COUNT(*) FROM sessions').fetchone()
print(f"\nTotal sessions: {sessions[0]}")
c.close()
