#!/bin/bash
set -euo pipefail

BASE="http://localhost:8051"

echo "=== 1. Login ==="
LOGIN=$(curl -s -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@grades.com","password":"secret123"}')
echo "$LOGIN" | python3 -m json.tool || echo "$LOGIN"
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

echo ""
echo "=== 2. List classes ==="
CLASSES=$(curl -s "$BASE/api/classes" -H "Authorization: Bearer $TOKEN")
echo "$CLASSES" | python3 -c "
import sys,json
data = json.load(sys.stdin)
if data:
    for c in data:
        print(f'  ID {c[\"id\"]}: {c[\"name\"]} ({c[\"subject\"]})')
else:
    print('  No classes yet')
"

echo ""
echo "=== 3. Create new class ==="
CLASS=$(curl -s -X POST "$BASE/api/classes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Algebra I","subject":"Math"}')
echo "$CLASS" | python3 -m json.tool || echo "$CLASS"
CID=$(echo "$CLASS" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo ""
echo "=== 4. Categories ==="
curl -s "$BASE/api/classes/$CID/categories" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo ""
echo "=== 5. Batch Add Students ==="
RESULT=$(curl -s -X POST "$BASE/api/classes/$CID/students/batch" \
  -H "Authorization: Bearer $TOKEN" \
  -d 'students_json=[{"first_name":"Alice","last_name":"Johnson"},{"first_name":"Bob","last_name":"Smith"},{"first_name":"Carol","last_name":"Williams"},{"first_name":"David","last_name":"Brown"}]')
echo "$RESULT" | python3 -m json.tool || echo "$RESULT"

echo ""
echo "=== 6. List Students ==="
STUDENTS=$(curl -s "$BASE/api/classes/$CID/students" -H "Authorization: Bearer $TOKEN")
echo "$STUDENTS" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for s in data:
    print(f\"  ID {s['id']}: {s['first_name']} {s['last_name']}\")
"

S1=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
S2=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[1]['id'])")
S3=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[2]['id'])")
S4=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[3]['id'])")

echo ""
echo "=== 7. Create Assignments ==="
A1_RESULT=$(curl -s -X POST "$BASE/api/classes/$CID/assignments" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Midterm","max_score":100,"category_id":1}')
A1=$(echo "$A1_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  Midterm (ID $A1, max 100)"

A2_RESULT=$(curl -s -X POST "$BASE/api/classes/$CID/assignments" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Homework 1","max_score":20,"category_id":2}')
A2=$(echo "$A2_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  Homework 1 (ID $A2, max 20)"

echo ""
echo "=== 8. Enter Grades ==="
for sid in $S1 $S2 $S3 $S4; do
  curl -s -X POST "$BASE/api/classes/$CID/grades" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"student_id\":$sid,\"assignment_id\":$A1,\"score\":$((RANDOM % 40 + 60))}" > /dev/null
  curl -s -X POST "$BASE/api/classes/$CID/grades" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"student_id\":$sid,\"assignment_id\":$A2,\"score\":$((RANDOM % 10 + 11))}" > /dev/null
done
echo "  Entered grades for 4 students x 2 assignments"

echo ""
echo "=== 9. Gradebook View ==="
curl -s "$BASE/api/classes/$CID/gradebook" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
d = json.load(sys.stdin)
print(f\"Class: {d['class']['name']} ({d['class']['subject']})\")
print(f\"Students: {len(d['students'])}  Assignments: {len(d['assignments'])}\")
for s in d['students']:
    print(f\"  {s['name']}: {s['average']:.1f}% ({s['letter']})\")
print(f\"\nClass average: {d['stats']['class_average']:.1f}%\")
print(f\"Top: {d['stats']['top_performer']['name']} ({d['stats']['top_performer']['average']:.1f}%)\")
print(f\"Distribution: {d['stats']['grade_distribution']}\")
"

echo ""
echo "=== 10. Analytics ==="
curl -s "$BASE/api/classes/$CID/analytics" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
d = json.load(sys.stdin)
o = d['overview']
print(f\"Students: {o['student_count']}  Class Avg: {o['class_average']:.1f}%\")
print(f\"Distribution: {o['grade_distribution']}\")
needs = [s['name'] for s in o.get('needs_support',[])]
if needs: print(f'Needs support: {needs}')
print()
for aname, astats in d['assignment_breakdown'].items():
    print(f\"  {aname}: avg={astats['average']:.0f}, min={astats['min_score']}, max={astats['max_score']}\")
"

echo ""
echo "=== 11. CSV Export ==="
curl -s "$BASE/api/classes/$CID/export/csv" \
  -H "Authorization: Bearer $TOKEN" | head -5

echo ""
echo "=== 12. Frontend ==="
echo -n "  Index: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/"
echo -n "  CSS: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/css/app.css"
echo -n "  JS: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/js/app.js"
echo ""

echo ""
echo "=== ALL DONE ==="
