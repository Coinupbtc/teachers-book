#!/bin/bash
set -eu

BASE="http://localhost:8051"

echo "=== 1. Login ==="
LOGIN=$(curl -s -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@grades.com","password":"secret123"}')
echo "$LOGIN"
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

echo ""
echo "=== 2. List classes ==="
CLASSES=$(curl -s "$BASE/api/classes" -H "Authorization: Bearer $TOKEN")
echo "$CLASSES"

# Get or create class
CID=$(echo "$CLASSES" | python3 -c "
import sys,json
d = json.load(sys.stdin)
if d:
    print(d[0]['id'])
else:
    print(0)
")

if [ "$CID" = "0" ]; then
  echo "=== Creating new class ==="
  CLASS=$(curl -s -X POST "$BASE/api/classes" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"Algebra I","subject":"Math"}')
  echo "$CLASS"
  CID=$(echo "$CLASS" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
fi
echo "Using class ID: $CID"

echo ""
echo "=== 3. Categories ==="
CATS=$(curl -s "$BASE/api/classes/$CID/categories" -H "Authorization: Bearer $TOKEN")
echo "$CATS" | python3 -m json.tool

echo ""
echo "=== 4. Batch Add Students ==="
STUDENT_RESULT=$(curl -s -X POST "$BASE/api/classes/$CID/students/batch" \
  -H "Authorization: Bearer $TOKEN" \
  -d 'students_json=[{"first_name":"Alice","last_name":"Johnson"},{"first_name":"Bob","last_name":"Smith"},{"first_name":"Carol","last_name":"Williams"},{"first_name":"David","last_name":"Brown"}]')
echo "$STUDENT_RESULT"

echo ""
echo "=== 5. List Students ==="
STUDENTS=$(curl -s "$BASE/api/classes/$CID/students" -H "Authorization: Bearer $TOKEN")
echo "$STUDENTS" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for s in data:
    print(f'  ID {s[\"id\"]}: {s[\"first_name\"]} {s[\"last_name\"]}')
"

S1=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
S2=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[1]['id'])")
S3=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[2]['id'])")
S4=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[3]['id'])")

echo ""
echo "=== 6. Create Assignments ==="
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
echo "=== 7. Enter Grades ==="
curl -s -X POST "$BASE/api/classes/$CID/grades" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"student_id\":$S1,\"assignment_id\":$A1,\"score\":88}" > /dev/null
curl -s -X POST "$BASE/api/classes/$CID/grades" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"student_id\":$S2,\"assignment_id\":$A1,\"score\":72}" > /dev/null
curl -s -X POST "$BASE/api/classes/$CID/grades" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"student_id\":$S3,\"assignment_id\":$A1,\"score\":95}" > /dev/null
curl -s -X POST "$BASE/api/classes/$CID/grades" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"student_id\":$S4,\"assignment_id\":$A1,\"score\":67}" > /dev/null
curl -s -X POST "$BASE/api/classes/$CID/grades" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"student_id\":$S1,\"assignment_id\":$A2,\"score\":18}" > /dev/null
curl -s -X POST "$BASE/api/classes/$CID/grades" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"student_id\":$S2,\"assignment_id\":$A2,\"score\":14}" > /dev/null
curl -s -X POST "$BASE/api/classes/$CID/grades" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"student_id\":$S3,\"assignment_id\":$A2,\"score\":19}" > /dev/null
curl -s -X POST "$BASE/api/classes/$CID/grades" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"student_id\":$S4,\"assignment_id\":$A2,\"score\":12}" > /dev/null
echo "  Done"

echo ""
echo "=== 8. Gradebook View ==="
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
echo "=== 9. Analytics ==="
curl -s "$BASE/api/classes/$CID/analytics" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
d = json.load(sys.stdin)
o = d['overview']
print(f\"Students: {o['student_count']}  Class Avg: {o['class_average']:.1f}%\")
print(f\"Distribution: {o['grade_distribution']}\")
needs = [s['name'] for s in o.get('needs_support',[])]
if needs: print(f'Needs support: {needs}')
for aname, astats in d['assignment_breakdown'].items():
    print(f\"  {aname}: avg={astats['average']:.0f}, min={astats['min_score']}, max={astats['max_score']}\")
"

echo ""
echo "=== 10. CSV Export ==="
curl -s "$BASE/api/classes/$CID/export/csv" \
  -H "Authorization: Bearer $TOKEN" | head -6

echo ""
echo "=== 11. Frontend ==="
echo -n "  Index: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/"
echo -n "  CSS: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/css/app.css"
echo -n "  JS: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/js/app.js"
echo ""

echo ""
echo "=== ALL DONE ==="
