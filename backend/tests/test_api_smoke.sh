#!/bin/bash
# Teachers Book — consolidated live-API smoke test (replaces test_wf.sh, test_wf2.sh,
# test_workflow.sh, test_final.sh). Single deterministic entrypoint.
#
# Usage:
#   ./setup.sh            # start the app (http://127.0.0.1:8010/)
#   backend/tests/test_api_smoke.sh            # against default URL
#   TEACHERS_BOOK_URL=http://localhost:8010 backend/tests/test_api_smoke.sh
#
# Exits non-zero on the first failing check (set -euo pipefail).
set -euo pipefail

BASE="${TEACHERS_BOOK_URL:-http://127.0.0.1:8010}"

fail() { echo "FAIL: $1" >&2; exit 1; }
jget() { python3 -c "import sys,json; d=json.load(sys.stdin); print(eval('d'+sys.argv[1]))" "$1"; }

echo "=== 1. Login ==="
LOGIN=$(curl -sf -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@grades.com","password":"secret123"}') || fail "login request"
TOKEN=$(echo "$LOGIN" | jget "['token']") || fail "no token in login response"
echo "  Logged in OK"

AUTH="Authorization: Bearer $TOKEN"

echo "=== 2. Create class ==="
CLASS=$(curl -sf -X POST "$BASE/api/classes" \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"name":"Algebra I","subject":"Math"}') || fail "create class"
CID=$(echo "$CLASS" | jget "['id']") || fail "no class id"
echo "  Class ID: $CID"

echo "=== 3. Categories ==="
CATS=$(curl -sf "$BASE/api/classes/$CID/categories" -H "$AUTH") || fail "list categories"
N=$(echo "$CATS" | jget "|len()")
[ "$N" -ge 1 ] || fail "expected >=1 category, got $N"
echo "  $N categories present"

echo "=== 4. Add students ==="
curl -sf -X POST "$BASE/api/classes/$CID/students/batch" \
  -H "$AUTH" \
  -d 'students_json=[{"first_name":"Alice","last_name":"Johnson"},{"first_name":"Bob","last_name":"Smith"},{"first_name":"Carol","last_name":"Williams"},{"first_name":"David","last_name":"Brown"}]' > /dev/null \
  || fail "batch add students"
STUDENTS=$(curl -sf "$BASE/api/classes/$CID/students" -H "$AUTH") || fail "list students"
S1=$(echo "$STUDENTS" | jget "[0]['id']"); S2=$(echo "$STUDENTS" | jget "[1]['id']")
S3=$(echo "$STUDENTS" | jget "[2]['id']"); S4=$(echo "$STUDENTS" | jget "[3]['id']")
echo "  Students: $S1 $S2 $S3 $S4"

echo "=== 5. Create assignments ==="
A1=$(curl -sf -X POST "$BASE/api/classes/$CID/assignments" \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"name":"Midterm","max_score":100,"category_id":1}' | jget "['id']") || fail "assignment 1"
A2=$(curl -sf -X POST "$BASE/api/classes/$CID/assignments" \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"name":"Homework 1","max_score":20,"category_id":2}' | jget "['id']") || fail "assignment 2"
echo "  Midterm=$A1 Homework1=$A2"

echo "=== 6. Enter grades (deterministic) ==="
for sid in "$S1" "$S2" "$S3" "$S4"; do
  curl -sf -X POST "$BASE/api/classes/$CID/grades" \
    -H "Content-Type: application/json" -H "$AUTH" \
    -d "{\"student_id\":$sid,\"assignment_id\":$A1,\"score\":88}" > /dev/null || fail "grade A1 for $sid"
  curl -sf -X POST "$BASE/api/classes/$CID/grades" \
    -H "Content-Type: application/json" -H "$AUTH" \
    -d "{\"student_id\":$sid,\"assignment_id\":$A2,\"score\":15}" > /dev/null || fail "grade A2 for $sid"
done
echo "  Entered 8 grades"

echo "=== 7. Gradebook ==="
GB=$(curl -sf "$BASE/api/classes/$CID/gradebook" -H "$AUTH") || fail "gradebook"
echo "$GB" | python3 -c "
import sys,json
d=json.load(sys.stdin)
assert len(d['students'])==4, 'expected 4 students'
assert len(d['assignments'])>=2, 'expected >=2 assignments'
print(f\"  Students: {len(d['students'])}  Assignments: {len(d['assignments'])}\")
print(f\"  Class avg: {d['stats']['class_average']:.1f}%\")
" || fail "gradebook shape"

echo "=== 8. Analytics ==="
AN=$(curl -sf "$BASE/api/classes/$CID/analytics" -H "$AUTH") || fail "analytics"
echo "$AN" | python3 -c "
import sys,json
o=json.load(sys.stdin)['overview']
assert o['student_count']==4, 'expected 4 students in analytics'
print(f\"  Students: {o['student_count']}  Avg: {o['class_average']:.1f}%\")
" || fail "analytics shape"

echo "=== 9. CSV export ==="
CSV=$(curl -sf "$BASE/api/classes/$CID/export/csv" -H "$AUTH") || fail "csv export"
echo "$CSV" | head -2

echo "=== 10. Frontend assets ==="
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
[ "$CODE" = "200" ] || fail "index returned $CODE"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/css/app.css")
[ "$CODE" = "200" ] || fail "css returned $CODE"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/js/app.js")
[ "$CODE" = "200" ] || fail "js returned $CODE"
echo "  index/css/js all 200"

echo ""
echo "=== ALL CHECKS PASSED ==="
