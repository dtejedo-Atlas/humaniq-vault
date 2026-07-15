"""Lista todos los users en Atlas con datos clave."""
from db_connection import get_db

db = get_db()
users = list(db.users.find({}, {"id": 1, "email": 1, "name": 1, "role": 1, "is_active": 1, "created_at": 1, "last_login": 1}).sort("created_at", 1))

print(f"\nTotal users: {len(users)}\n")
print(f"{'EMAIL':<42}{'NAME':<28}{'ROLE':<13}{'ACTIVE':<8}{'CREATED':<22}{'LAST_LOGIN':<22}")
print("-" * 135)
for u in users:
    created = str(u.get("created_at", ""))[:19]
    last_login = str(u.get("last_login", ""))[:19] if u.get("last_login") else "-"
    print(f"{u.get('email',''):<42}{(u.get('name') or '')[:26]:<28}{u.get('role',''):<13}{str(u.get('is_active')):<8}{created:<22}{last_login:<22}")
