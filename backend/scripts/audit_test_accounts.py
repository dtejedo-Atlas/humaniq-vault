from db_connection import get_db

TEST_EMAILS = [
    "test_user_011349@atlas.com",
    "test_user_011402@atlas.com",
    "test_user_b3fc4cd1@atlas.com",
    "test_user_a7068b0c@atlas.com",
    "test_user_fa5b2128@atlas.com",
    "recruiter_test@atlas.com",
    "test_utf8@atlas.com",
]

db = get_db()
print(f"\n{'EMAIL':<32}{'ROL':<13}{'ACTIVO':<8}{'CAND.SUBIDOS':<14}{'NOTAS':<7}{'ASIGN(hechas/recibidas)':<25}{'ACTIVITY_LOG':<13}")
print("-" * 112)
for email in TEST_EMAILS:
    u = db.users.find_one({"email": email}, {"id": 1, "role": 1, "is_active": 1})
    if not u:
        print(f"{email:<32}NO EXISTE")
        continue
    uid = u["id"]
    cands = db.candidates.count_documents({"uploaded_by": uid})
    notes = db.candidates.count_documents({"notes.created_by": uid})
    assign_made = db.assignments.count_documents({"assigned_by": uid})
    assign_recv = db.assignments.count_documents({"recruiter_id": uid})
    job_assign = db.candidates.count_documents({"job_assignments.assigned_by": uid})
    logs = db.activity_logs.count_documents({"user_id": uid})
    print(f"{email:<32}{u.get('role',''):<13}{str(u.get('is_active')):<8}{cands:<14}{notes:<7}{f'{assign_made + job_assign}/{assign_recv}':<25}{logs:<13}")
