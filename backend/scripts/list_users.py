from db_connection import get_db

db = get_db()
users = list(db.users.find({}, {'email': 1, 'name': 1, 'role': 1, 'is_active': 1}))
invitations = {i['email']: i.get('status') for i in db.invitations.find({}, {'email': 1, 'status': 1})}

print(f"\n=== USUARIOS EN ATLAS ({len(users)}) ===")
for u in users:
    inv = invitations.get(u['email'], '-')
    print(f"  {u['email']:<35} rol={u.get('role'):<15} activo={u.get('is_active')}  invitación={inv}")

pending = [e for e, s in invitations.items() if s == 'pending']
print(f"\n=== INVITACIONES PENDIENTES ({len(pending)}) ===")
for e in pending:
    print(f"  {e}")
