#!/bin/bash
set -eu

BASE="http://localhost:8051"

echo "=== 1. Login ==="
LOGIN=$(curl -s -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@grades.com","password":"secret123"}')
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

CID=1
echo "Class ID: $CID"

echo ""
echo "=== 2. Add students (fresh) ==="
# Clear existing students & assignments first via a new class, or add more
curl -s -X POST "$BASE/api/classes/$CID/students/batch" \
  -H "Authorization: Bearer $TOKEN" \
  -d 'students_json=[{"first_name":"Alice","last_name":"Johnson"},{"first_name":"Bob","last_name":"Smith"},{"first_name":"Carol","last_name":"Williams"},{"first_name":"David","last_name":"Brown"}]'

echo ""
echo "=== 3. Students ==="
STUDENTS=$(curl -s "$BASE/api/classes/$CID/students" -H "Authorization: Bearer $TOKEN")
STUDENTS_FILE=$(echo "$STUDENTS" | python3 -c "
import sys,json
data = json.load(sys.stdin)
# get unique by name
seen=set()
uniq=[]
for s in data:
    n=s['first_name']
    if n not in seen:
        seen.add(n)
        uniq.append(s)
# just use first 4
for s in uniq[:4]:
    print(s['id'])
")
SIDS=($STUDENTS_FILE)
echo "Student IDs: ${SIDS[*]}"

echo ""
echo "=== 4. Categories ==="
curl -s "$BASE/api/classes/$CID/categories" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
for c in json.load(sys.stdin):
    print(f\"  ID {c['id']}: {c['name']} ({c['weight_pct']}%)\")
"

echo ""
echo "=== 5. Create Assignments ==="
for pair in "1:1" "2:2" "3:2"; do
  IFS=':' read -r num cat <<< "$pair"
  NAME="Midterm"
  SCORE=100
  [ "$num" = "2" ] && NAME="Homework 1" && SCORE=20
  [ "$num" = "3" ] && NAME="Quiz 1" && SCORE=30
  AID=$(curl -s -X POST "$BASE/api/classes/$CID/assignments" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"$NAME\",\"max_score\":$SCORE,\"category_id\":$cat}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "  Created \"$NAME\" (ID $AID, max $SCORE)"
done

echo ""
echo "=== 6. Get Grade IDs ==="
curl -s "$BASE/api/classes/$CID/gradebook" -H "Authorization: Bearer $TOKEN" > /tmp/gb3.json
python3 -c "
import json
d = json.load(open('/tmp/gb3.json'))
print('  Grade IDs:')
for s in d['students']:
    for aid, g in s['grades'].items():
        print(f'    {s[\"name\"]} assign {aid}: grade_id={g[\"grade_id\"]} (score {g[\"score\"]})')
" > /tmp/grade_map.txt
cat /tmp/grade_map.txt

echo ""
echo "=== 7. Update grades via PUT ==="
python3 -c "
import json, subprocess

d = json.load(open('/tmp/gb3.json'))
token = open('/dev/stdin').read().strip()
assignments = {str(a['id']): a for a in d['assignments']}

scores = {
    'Alice Johnson':  {'1': 88, '2': 18, '3': 25},
    'Bob Smith':      {'1': 72, '2': 14, '3': 20},
    'Carol Williams': {'1': 95, '2': 19, '3': 28},
    'David Brown':    {'1': 67, '2': 12, '3': 15},
}

for s in d['students']:
    name = s['name']
    for aid, g in s['grades'].items():
        score = scores[name][aid]
        grade_id = g['grade_id']
        r = subprocess.run([
            'curl', '-s', '-X', 'PUT',
            f'http://localhost:8051/api/grades/{grade_id}',
            '-H', 'Content-Type: application/json',
            '-H', f'Authorization: Bearer {token}',
            '-d', json.dumps({'score': score})
        ], capture_output=True, text=True)
        print(f\"  {name}: assign {aid} -> {score}/100 ({r.stdout})\")
" <<< "$TOKEN"

echo ""
echo "=== 8. Gradebook ==="
curl -s "$BASE/api/classes/$CID/gradebook" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
d = json.load(sys.stdin)
print(f\"Class: {d['class']['name']} | Students: {len(d['students'])}\")
for s in d['students']:
    print(f'  {s[\"name\"]}: {s[\"average\"]:.1f}% ({s[\"letter\"]})')
print(f\"\nClass avg: {d['stats']['class_average']:.1f}%\")
print(f\"Top: {d['stats']['top_performer']['name']} ({d['stats']['top_performer']['average']:.1f}%)\")
print(f\"Distribution: {d['stats']['grade_distribution']}\")
"

echo ""
echo "=== 9. Analytics ==="
curl -s "$BASE/api/classes/$CID/analytics" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
d = json.load(sys.stdin)
o = d['overview']
print(f\"Students: {o['student_count']}  Avg: {o['class_average']:.1f}%\")
print(f\"Distribution: {o['grade_distribution']}\")
needs = [s['name'] for s in o.get('needs_support',[])]
if needs: print(f'Needs support: {needs}')
for aname, astats in d['assignment_breakdown'].items():
    print(f\"  {aname}: avg={astats['average']:.0f}, min={astats['min_score']}, max={astats['max_score']}\")
"

echo ""
echo "=== 10. CSV Export ==="
curl -s "$BASE/api/classes/$CID/export/csv" -H "Authorization: Bearer $TOKEN" | head -6

echo ""
echo "=== 11. Frontend ==="
echo -n "  Index: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/"
echo -n "  CSS: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/css/app.css"
echo -n "  JS: "; curl -s -o /dev/null -w "%{http_code}" "$BASE/js/app.js"
echo ""

echo ""
echo "=== ALL DONE ==="
