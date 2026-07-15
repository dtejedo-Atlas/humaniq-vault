"""Limpieza final Atlas:
- Desactiva 6 cuentas de prueba (test_user_* + recruiter_test)
- Desactiva cuentas viejas @atlas.com reemplazadas por invitaciones a humaniq/hqts
- Rota password de test_utf8@atlas.com (imprime nueva password en consola una sola vez)
"""
import secrets
import string
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")
from auth import get_password_hash  # noqa
from db_connection import get_db  # noqa

TEST_TO_DEACTIVATE = [
    "test_user_011349@atlas.com",
    "test_user_011402@atlas.com",
    "test_user_b3fc4cd1@atlas.com",
    "test_user_a7068b0c@atlas.com",
    "test_user_fa5b2128@atlas.com",
    "recruiter_test@atlas.com",
]

OLD_REPLACED = [
    "patricia@atlas.com",     # -> psaez@humaniq.com.mx
    "ximena@atlas.com",       # -> xsanchez@humaniq.com.mx
    "alejandra@atlas.com",    # -> arosas@hqts.com.mx
    "viridiana@atlas.com",    # -> vguerrero@hqts.com.mx
]

# admin@atlas.com también es viejo test - lo dejo por ahora, no está en la instruccion del user

ROTATE_TEST_UTF8 = "test_utf8@atlas.com"


def gen_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*+-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def deactivate(db, emails, tag):
    print(f"\n== Desactivando {tag} ==")
    for email in emails:
        u = db.users.find_one({"email": email})
        if not u:
            print(f"  [SKIP] {email} no existe")
            continue
        if u.get("is_active") is False:
            print(f"  [YA] {email} ya inactivo")
            continue
        res = db.users.update_one(
            {"email": email},
            {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc).isoformat()}}
        )
        print(f"  [OK] {email} -> is_active=False (modified={res.modified_count})")


def rotate_password(db, email):
    print(f"\n== Rotando password de {email} ==")
    u = db.users.find_one({"email": email})
    if not u:
        print(f"  [ERROR] {email} no existe")
        return None
    new_pwd = gen_password(20)
    new_hash = get_password_hash(new_pwd)
    res = db.users.update_one(
        {"email": email},
        {"$set": {"password_hash": new_hash, "password_rotated_at": datetime.now(timezone.utc).isoformat()}}
    )
    print(f"  [OK] modified={res.modified_count}")
    print(f"  NUEVA PASSWORD (guarda en test_credentials.md): {new_pwd}")
    return new_pwd


def main():
    db = get_db()
    deactivate(db, TEST_TO_DEACTIVATE, "6 cuentas de prueba")
    deactivate(db, OLD_REPLACED, "cuentas viejas @atlas.com reemplazadas")
    new_pwd = rotate_password(db, ROTATE_TEST_UTF8)

    # Verificación final
    print("\n== Estado final de cuentas afectadas ==")
    all_touched = TEST_TO_DEACTIVATE + OLD_REPLACED + [ROTATE_TEST_UTF8]
    for email in all_touched:
        u = db.users.find_one({"email": email}, {"email": 1, "is_active": 1, "role": 1})
        if u:
            print(f"  {email:<40} active={u.get('is_active')}  role={u.get('role')}")

    # Guardar password nueva en archivo temporal
    if new_pwd:
        with open("/tmp/new_test_utf8_password.txt", "w") as f:
            f.write(new_pwd)
        print(f"\nPassword nueva guardada temporalmente en /tmp/new_test_utf8_password.txt")


if __name__ == "__main__":
    main()
