"""Create seed data for E2E frontend test — writes IDs to /tmp/e2e_ids.json"""
import json, os, time, requests

BASE = "https://atlas-recruiting-ai.preview.emergentagent.com"
API = f"{BASE}/api"

r = requests.post(f"{API}/auth/login", json={"email": "test_utf8@atlas.com", "password": "Humaniq123"}, timeout=30)
assert r.status_code == 200, r.text
tok = r.json()["access_token"]
hdr = {"Authorization": f"Bearer {tok}"}

ind = "manufacturing"
fa = "supply_chain"

ts = int(time.time())

# candidate
r = requests.post(f"{API}/candidates", headers=hdr, json={
    "full_name": f"TEST_E2E Candidate {ts}",
    "email": f"test_e2e_cand_{ts}@example.com",
    "country": "México",
}, timeout=20)
assert r.status_code in (200, 201), r.text
cand = r.json()

# Two jobs
def mkjob(letter):
    r = requests.post(f"{API}/jobs", headers=hdr, json={
        "title": f"TEST_E2E Job {letter} {ts}",
        "company": f"TEST_E2E Co {letter}",
        "industry": ind,
        "functional_area": fa,
        "seniority": "senior",
        "min_experience": 0,
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()

jobA = mkjob("A")
jobB = mkjob("B")

data = {
    "token": tok,
    "cand_id": cand["id"],
    "cand_name": cand["full_name"],
    "job_a_id": jobA["id"],
    "job_a_title": jobA["title"],
    "job_b_id": jobB["id"],
    "job_b_title": jobB["title"],
}
with open("/app/test_reports/e2e_ids.json", "w") as fh:
    json.dump(data, fh, indent=2)
print(json.dumps(data, indent=2))
