import json

r = json.load(open(r"C:\Users\Malik\desktop\POS-Project\diag_report.json"))
print(f"Report ID: {r['id']}")
print(f"Live: {r['is_live']}  QB Accounts: {r['total_qb_accounts']}")
print(f"Grade: {r['health_grade']}  Matched:{r['matched']}  Candidates:{r['candidates']}  Unmatched:{r['unmatched']}  Coverage:{r['coverage_pct']}%")
print()

pending = []
for i, item in enumerate(r["items"]):
    s = item["status"]
    d = item.get("decision", "")
    b = item.get("best_match") or {}
    bn = b.get("qb_account_name", "-")
    bi = b.get("qb_account_id", "-")
    bs = b.get("score", 0)
    if d:
        dn = item.get("decision_account_name", "-")
        print(f"  OK [{i:2d}] {item['template_account_name']:40s} -> {d}: {dn}")
    else:
        cs = item.get("candidates", [])
        print(f"  >> [{i:2d}] {s:12s} {item['template_account_name']:40s} best={bn} (id={bi}, score={bs:.2f})")
        for c in cs[:4]:
            print(f"               cand: {c['qb_account_name']} (id={c['qb_account_id']}, score={c['score']:.2f}, type={c['qb_account_type']})")
        pending.append(i)

print(f"\nPending indices: {pending}")
print(f"Total pending: {len(pending)}")
