#!/bin/bash
set -eu

BASE="http://localhost:8051"

echo "=== 1. Login ==="
LOGIN=$(curl -s -X POST "$BASE/api/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@grades.com","password":"secret123"}')
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "  Logged in OK"

echo ""
echo "=== 2. Create Class ==="
CLASS=$(curl -s -X POST "$BASE/api/classes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Algebra I","subject":"Math"}')
CID=$(echo "$CLASS" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  Class ID: $CID"

echo ""
echo "=== 3. Categories ==="
curl -s "$BASE/api/classes/$CID/categories" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
for c in json.load(sys.stdin):
    print(f\"  ID {c['id']}: {c['name']} ({c['weight_pct']}%)\")
"

echo ""
echo "=== 4. Add Students ==="
curl -s -X POST "$BASE/api/classes/$CID/students/batch" \
  -H "Authorization: Bearer $TOKEN" \
  -d 'students_json=[{"first_name":"Alice","last_name":"Johnson"},{"first_name":"Bob","last_name":"Smith"},{"first_name":"Carol","last_name":"Williams"},{"first_name":"David","last_name":"Brown"}]'
echo ""

echo ""
echo "=== 5. Students ==="
STUDENTS=$(curl -s "$BASE/api/classes/$CID/students" -H "Authorization: Bearer $TOKEN")
echo "$STUDENTS" | python3 -c "
import sys,json
for s in json.load(sys.stdin):
    print(f\"  ID {s['id']}: {s['first_name']} {s['last_name']}\")
"
S1=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
S2=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[1]['id'])")
S3=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[2]['id'])")
S4=$(echo "$STUDENTS" | python3 -c "import sys,json; print(json.load(sys.stdin)[3]['id'])")

echo ""
echo "=== 6. Create Assignments ==="
for pair in "1:1" "2:2" "3:6"; do
  IFS=':' read -r num cat <<< "$pair"
  case "$num" in
    1) NAME="Midterm"; SCORE=100 ;;
    2) NAME="Homework 1"; SCORE=20 ;;
    3) NAME="Quiz 1"; SCORE=30 ;;
  esac
  AID=$(curl -s -X POST "$BASE/api/classes/$CID/assignments" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"$NAME\",\"max_score\":$SCORE,\"category_id\":$cat}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "  \"$NAME\" (ID $AID, max $SCORE, cat $cat)"
done

echo ""
echo "=== 7. Update Grades via PUT ==="
# Get gradebook and build grade_id→score mapping
curl -s "$BASE/api/classes/$CID/gradebook" -H "Authorization: Bearer $TOKEN" > /tmp/gb_final.json

python3 -c "
import json, subprocess, sys

d = json.load(open('/tmp/gb_final.json'))
token = open('/dev/stdin').read().strip()

# Find new assignment IDs (filter out old ones by looking at gradebook assignments list)
# Get latest 3 assignments
assignments = sorted(d['assignments'], key=lambda x: x['id'])[-3:]
print(f'  Using assignments: {[(a[\"id\"], a[\"name\"]) for a in assignments]}')
aid_map = {a['name']: str(a['id']) for a in assignments}

scores_map = {
    'Alice Johnson':  {'Midterm': 88, 'Homework 1': 18, 'Quiz 1': 25},
    'Bob Smith':      {'Midterm': 72, 'Homework 1': 14, 'Quiz 1': 20},
    'Carol Williams': {'Midterm': 95, 'Homework 1': 19, 'Quiz 1': 28},
    'David Brown':    {'Midterm': 67, 'Homework 1': 12, 'Quiz 1': 15},
}

for s in d['students']:
    name = s['name']
    for aid, g in list(s['grades'].items()):
        # Find which assignment this ID corresponds to
        for aname, map_aid in aid_map.items():
            if aid == map_aid:
                score = scores_map[name][aname]
                grade_id = g['grade_id']
                r = subprocess.run([
                    'curl', '-s', '-X', 'PUT',
                    f'http://localhost:8051/api/grades/{grade_id}',
                    '-H', 'Content-Type: application/json',
                    '-H', f'Authorization: Bearer {token}',
                    '-d', json.dumps({'score': score})
                ], capture_output=True, text=True)
                print(f'  {name} - {aname}: {score} -> {r.stdout}')
                break
" <<< "$TOKEN"

echo ""
echo "=== 8. Gradebook ==="
curl -s "$BASE/api/classes/$CID/gradebook" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
d = json.load(sys.stdin)
print(f\"Class: {d['class']['name']} | Students: {len(d['students'])}\")
for s in d['students']:
    print(f\"  {s['name']}: {s['average']:.1f}% ({s['letter']})\")
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
