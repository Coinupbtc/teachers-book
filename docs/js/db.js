/**
 * Teachers B00k — IndexedDB store (offline, device-local).
 * Exposes window.TB with account + gradebook CRUD matching the former API shapes.
 */
(function (global) {
  "use strict";

  const DB_NAME = "teachers_b00k";
  const DB_VERSION = 1;
  // Backend default category weights (fractions). UI shows weight_pct.
  const DEFAULT_CATEGORIES = [
    { name: "Tests", weight: 0.35, sort_order: 0 },
    { name: "Quizzes", weight: 0.20, sort_order: 1 },
    { name: "Homework", weight: 0.20, sort_order: 2 },
    { name: "Classwork", weight: 0.15, sort_order: 3 },
    { name: "Participation", weight: 0.10, sort_order: 4 },
  ];

  let dbPromise = null;

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onerror = () => reject(req.error || new Error("IndexedDB open failed"));
      req.onupgradeneeded = () => {
        const db = req.result;
        const stores = [
          "meta",
          "accounts",
          "classes",
          "categories",
          "students",
          "assignments",
          "grades",
          "rewards",
          "goals",
          "benchmarks",
        ];
        for (const name of stores) {
          if (!db.objectStoreNames.contains(name)) {
            const store = db.createObjectStore(name, { keyPath: "id", autoIncrement: true });
            if (name === "classes") store.createIndex("account_id", "account_id", { unique: false });
            if (name === "categories") store.createIndex("class_id", "class_id", { unique: false });
            if (name === "students") store.createIndex("class_id", "class_id", { unique: false });
            if (name === "assignments") store.createIndex("class_id", "class_id", { unique: false });
            if (name === "grades") {
              store.createIndex("student_id", "student_id", { unique: false });
              store.createIndex("assignment_id", "assignment_id", { unique: false });
              store.createIndex("student_assignment", ["student_id", "assignment_id"], { unique: true });
            }
            if (name === "rewards") store.createIndex("class_id", "class_id", { unique: false });
            if (name === "goals") store.createIndex("class_id", "class_id", { unique: false });
            if (name === "benchmarks") store.createIndex("goal_id", "goal_id", { unique: false });
          }
        }
      };
      req.onsuccess = () => resolve(req.result);
    });
    return dbPromise;
  }

  function tx(storeNames, mode = "readonly") {
    return openDb().then((db) => db.transaction(storeNames, mode));
  }

  function reqToPromise(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /** Resolve when an IDB transaction finishes (success, error, or abort). */
  function txDone(transaction) {
    return new Promise((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error || new Error("aborted"));
    });
  }

  function storeGetAll(store) {
    return reqToPromise(store.getAll());
  }

  function storeGet(store, id) {
    return reqToPromise(store.get(id));
  }

  function storePut(store, value) {
    return reqToPromise(store.put(value));
  }

  function storeAdd(store, value) {
    return reqToPromise(store.add(value));
  }

  function storeDelete(store, id) {
    return reqToPromise(store.delete(id));
  }

  function indexGetAll(index, key) {
    return reqToPromise(index.getAll(key));
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function displayName(first, last) {
    return `${first} ${last}`.trim();
  }

  function err(message) {
    return new Error(message);
  }

  // ── Accounts ──────────────────────────────────────────────────────────────

  async function listAccounts() {
    const t = await tx(["accounts"]);
    const rows = await storeGetAll(t.objectStore("accounts"));
    return rows.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
  }

  async function createAccount(name) {
    const trimmed = String(name || "").trim();
    if (!trimmed) throw err("Enter your name.");
    const t = await tx(["accounts"], "readwrite");
    const idPromise = storeAdd(t.objectStore("accounts"), {
      name: trimmed,
      created_at: nowIso(),
    });
    await Promise.all([idPromise, txDone(t)]);
    return { id: await idPromise, name: trimmed };
  }

  async function getAccount(id) {
    const t = await tx(["accounts"]);
    const account = await storeGet(t.objectStore("accounts"), Number(id));
    if (!account) throw err("Account not found on this device.");
    return account;
  }

  // ── Classes ───────────────────────────────────────────────────────────────

  async function listClasses(accountId) {
    const t = await tx(["classes", "students", "assignments"]);
    const classes = await indexGetAll(t.objectStore("classes").index("account_id"), Number(accountId));
    const students = await storeGetAll(t.objectStore("students"));
    const assignments = await storeGetAll(t.objectStore("assignments"));
    return classes
      .slice()
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
      .map((c) => ({
        id: c.id,
        name: c.name,
        subject: c.subject || "",
        semester: c.semester || "",
        student_count: students.filter((s) => s.class_id === c.id).length,
        assignment_count: assignments.filter((a) => a.class_id === c.id).length,
      }));
  }

  async function createClass(accountId, payload) {
    const cls = {
      account_id: Number(accountId),
      name: String(payload.name || "").trim(),
      subject: String(payload.subject || "").trim(),
      grade_level: String(payload.grade_level || "").trim(),
      semester: payload.semester || "Fall 2026",
      school_year: payload.school_year || "2026-2027",
      created_at: nowIso(),
    };
    if (!cls.name) throw err("Enter a class name.");
    const tClass = await tx(["classes"], "readwrite");
    const classIdPromise = storeAdd(tClass.objectStore("classes"), cls);
    await Promise.all([classIdPromise, txDone(tClass)]);
    const classId = await classIdPromise;
    const tCats = await tx(["categories"], "readwrite");
    const catStore = tCats.objectStore("categories");
    const catWrites = DEFAULT_CATEGORIES.map((cat) =>
      storeAdd(catStore, {
        class_id: classId,
        name: cat.name,
        weight: cat.weight,
        drop_lowest: 0,
        sort_order: cat.sort_order,
      })
    );
    await Promise.all([...catWrites, txDone(tCats)]);
    return { id: classId, name: cls.name };
  }

  async function assertClassOwner(classId, accountId) {
    const t = await tx(["classes"]);
    const cls = await storeGet(t.objectStore("classes"), Number(classId));
    if (!cls || cls.account_id !== Number(accountId)) throw err("Class not found");
    return cls;
  }

  // ── Categories ────────────────────────────────────────────────────────────

  async function listCategories(classId, accountId) {
    await assertClassOwner(classId, accountId);
    const t = await tx(["categories", "assignments"]);
    const cats = await indexGetAll(t.objectStore("categories").index("class_id"), Number(classId));
    const assignments = await indexGetAll(t.objectStore("assignments").index("class_id"), Number(classId));
    cats.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    const withPct = global.GradeComputer.withWeightPct(cats);
    return withPct.map((c) => ({
      id: c.id,
      name: c.name,
      weight: c.weight,
      weight_pct: c.weight_pct,
      drop_lowest: c.drop_lowest || 0,
      assignment_count: assignments.filter((a) => a.category_id === c.id).length,
    }));
  }

  // ── Students ──────────────────────────────────────────────────────────────

  async function addStudentsBatch(classId, accountId, rows) {
    await assertClassOwner(classId, accountId);
    const t = await tx(["students"], "readwrite");
    const store = t.objectStore("students");
    const writes = [];
    let count = 0;
    for (const row of rows) {
      const first = String(row.first_name || "").trim();
      const last = String(row.last_name || "Student").trim() || "Student";
      if (!first) continue;
      writes.push(
        storeAdd(store, {
          class_id: Number(classId),
          first_name: first,
          last_name: last,
          email: String(row.email || "").trim(),
          created_at: nowIso(),
        })
      );
      count += 1;
    }
    await Promise.all([...writes, txDone(t)]);
    return { status: "ok", count };
  }

  async function updateStudent(studentId, accountId, payload) {
    const tRead = await tx(["students", "classes"]);
    const student = await storeGet(tRead.objectStore("students"), Number(studentId));
    if (!student) throw err("Student not found");
    const cls = await storeGet(tRead.objectStore("classes"), student.class_id);
    if (!cls || cls.account_id !== Number(accountId)) throw err("Student not found");
    student.first_name = String(payload.first_name || "").trim();
    student.last_name = String(payload.last_name || "").trim();
    student.email = String(payload.email || "").trim();
    if (!student.first_name || !student.last_name) throw err("First and last name are required.");
    const tWrite = await tx(["students"], "readwrite");
    await Promise.all([storePut(tWrite.objectStore("students"), student), txDone(tWrite)]);
    return { status: "updated" };
  }

  async function deleteStudent(studentId, accountId) {
    const tRead = await tx(["students", "classes", "grades", "rewards", "goals", "benchmarks"]);
    const student = await storeGet(tRead.objectStore("students"), Number(studentId));
    if (!student) throw err("Student not found");
    const cls = await storeGet(tRead.objectStore("classes"), student.class_id);
    if (!cls || cls.account_id !== Number(accountId)) throw err("Student not found");

    const grades = await storeGetAll(tRead.objectStore("grades"));
    const gradeIds = grades.filter((g) => g.student_id === student.id).map((g) => g.id);
    const rewards = await storeGetAll(tRead.objectStore("rewards"));
    const rewardIds = rewards.filter((r) => r.student_id === student.id).map((r) => r.id);
    const goals = await storeGetAll(tRead.objectStore("goals"));
    const benchStore = tRead.objectStore("benchmarks");
    const goalIds = [];
    const benchIds = [];
    for (const goal of goals) {
      if (goal.student_id !== student.id) continue;
      goalIds.push(goal.id);
      const benches = await indexGetAll(benchStore.index("goal_id"), goal.id);
      benchIds.push(...benches.map((b) => b.id));
    }

    const tWrite = await tx(["students", "grades", "rewards", "goals", "benchmarks"], "readwrite");
    const deletes = [];
    for (const id of gradeIds) deletes.push(storeDelete(tWrite.objectStore("grades"), id));
    for (const id of rewardIds) deletes.push(storeDelete(tWrite.objectStore("rewards"), id));
    for (const id of benchIds) deletes.push(storeDelete(tWrite.objectStore("benchmarks"), id));
    for (const id of goalIds) deletes.push(storeDelete(tWrite.objectStore("goals"), id));
    deletes.push(storeDelete(tWrite.objectStore("students"), student.id));
    await Promise.all([...deletes, txDone(tWrite)]);
    return { status: "deleted" };
  }

  // ── Assignments ───────────────────────────────────────────────────────────

  async function createAssignment(classId, accountId, payload) {
    await assertClassOwner(classId, accountId);
    const name = String(payload.name || "").trim();
    const maxScore = Number(payload.max_score);
    if (!name) throw err("Enter an assignment name.");
    if (!Number.isFinite(maxScore) || maxScore <= 0) throw err("Points possible must be greater than zero.");
    const t = await tx(["assignments"], "readwrite");
    const idPromise = storeAdd(t.objectStore("assignments"), {
      class_id: Number(classId),
      category_id: payload.category_id != null ? Number(payload.category_id) : null,
      name,
      max_score: maxScore,
      due_date: payload.due_date || null,
      extra_credit: Boolean(payload.extra_credit),
      created_at: nowIso(),
    });
    await Promise.all([idPromise, txDone(t)]);
    return { id: await idPromise, status: "created" };
  }

  async function updateAssignment(assignmentId, accountId, payload) {
    const tRead = await tx(["assignments", "classes"]);
    const a = await storeGet(tRead.objectStore("assignments"), Number(assignmentId));
    if (!a) throw err("Assignment not found");
    const cls = await storeGet(tRead.objectStore("classes"), a.class_id);
    if (!cls || cls.account_id !== Number(accountId)) throw err("Assignment not found");
    a.name = String(payload.name || "").trim();
    a.max_score = Number(payload.max_score);
    a.due_date = payload.due_date || null;
    a.category_id = payload.category_id != null ? Number(payload.category_id) : null;
    a.extra_credit = Boolean(payload.extra_credit);
    if (!a.name) throw err("Enter an assignment name.");
    if (!Number.isFinite(a.max_score) || a.max_score <= 0) throw err("Points possible must be greater than zero.");
    const tWrite = await tx(["assignments"], "readwrite");
    await Promise.all([storePut(tWrite.objectStore("assignments"), a), txDone(tWrite)]);
    return { status: "updated" };
  }

  async function deleteAssignment(assignmentId, accountId) {
    const tRead = await tx(["assignments", "classes", "grades"]);
    const a = await storeGet(tRead.objectStore("assignments"), Number(assignmentId));
    if (!a) throw err("Assignment not found");
    const cls = await storeGet(tRead.objectStore("classes"), a.class_id);
    if (!cls || cls.account_id !== Number(accountId)) throw err("Assignment not found");
    const grades = await storeGetAll(tRead.objectStore("grades"));
    const gradeIds = grades.filter((g) => g.assignment_id === a.id).map((g) => g.id);

    const tWrite = await tx(["assignments", "grades"], "readwrite");
    const deletes = gradeIds.map((id) => storeDelete(tWrite.objectStore("grades"), id));
    deletes.push(storeDelete(tWrite.objectStore("assignments"), a.id));
    await Promise.all([...deletes, txDone(tWrite)]);
    return { status: "deleted" };
  }

  // ── Grades ────────────────────────────────────────────────────────────────

  async function upsertGrade(classId, accountId, payload) {
    await assertClassOwner(classId, accountId);
    const studentId = Number(payload.student_id);
    const assignmentId = Number(payload.assignment_id);
    const tRead = await tx(["grades", "students", "assignments"]);
    const student = await storeGet(tRead.objectStore("students"), studentId);
    const assignment = await storeGet(tRead.objectStore("assignments"), assignmentId);
    if (!student || student.class_id !== Number(classId)) throw err("Student must belong to this class");
    if (!assignment || assignment.class_id !== Number(classId)) throw err("Assignment must belong to this class");

    const all = await storeGetAll(tRead.objectStore("grades"));
    const existing = all.find((g) => g.student_id === studentId && g.assignment_id === assignmentId);
    const record = {
      student_id: studentId,
      assignment_id: assignmentId,
      score: Number(payload.score) || 0,
      max_score: payload.max_score != null ? Number(payload.max_score) : null,
      is_excused: Boolean(payload.is_excused),
      late: Boolean(payload.late),
      comments: String(payload.comments || ""),
      graded_at: nowIso(),
    };
    const tWrite = await tx(["grades"], "readwrite");
    const gradeStore = tWrite.objectStore("grades");
    if (existing) {
      record.id = existing.id;
      await Promise.all([storePut(gradeStore, record), txDone(tWrite)]);
      return { id: existing.id, status: "updated" };
    }
    const idPromise = storeAdd(gradeStore, record);
    await Promise.all([idPromise, txDone(tWrite)]);
    return { id: await idPromise, status: "created" };
  }

  async function updateGrade(gradeId, accountId, payload) {
    const tRead = await tx(["grades", "students", "classes"]);
    const grade = await storeGet(tRead.objectStore("grades"), Number(gradeId));
    if (!grade) throw err("Grade not found");
    const student = await storeGet(tRead.objectStore("students"), grade.student_id);
    const cls = student ? await storeGet(tRead.objectStore("classes"), student.class_id) : null;
    if (!cls || cls.account_id !== Number(accountId)) throw err("Grade not found");
    grade.score = Number(payload.score) || 0;
    if (payload.max_score != null) grade.max_score = Number(payload.max_score);
    grade.is_excused = Boolean(payload.is_excused);
    grade.late = Boolean(payload.late);
    grade.comments = String(payload.comments || "");
    grade.graded_at = nowIso();
    const tWrite = await tx(["grades"], "readwrite");
    await Promise.all([storePut(tWrite.objectStore("grades"), grade), txDone(tWrite)]);
    return { status: "updated" };
  }

  async function deleteGrade(gradeId, accountId) {
    const tRead = await tx(["grades", "students", "classes"]);
    const grade = await storeGet(tRead.objectStore("grades"), Number(gradeId));
    if (!grade) throw err("Grade not found");
    const student = await storeGet(tRead.objectStore("students"), grade.student_id);
    const cls = student ? await storeGet(tRead.objectStore("classes"), student.class_id) : null;
    if (!cls || cls.account_id !== Number(accountId)) throw err("Grade not found");
    const tWrite = await tx(["grades"], "readwrite");
    await Promise.all([storeDelete(tWrite.objectStore("grades"), grade.id), txDone(tWrite)]);
    return { status: "deleted" };
  }

  // ── Gradebook assembly ────────────────────────────────────────────────────

  async function getGradebook(classId, accountId) {
    const cls = await assertClassOwner(classId, accountId);
    const t = await tx(["students", "assignments", "grades", "categories"]);
    const students = (await indexGetAll(t.objectStore("students").index("class_id"), Number(classId)))
      .slice()
      .sort((a, b) => a.last_name.localeCompare(b.last_name) || a.first_name.localeCompare(b.first_name));
    const assignments = (await indexGetAll(t.objectStore("assignments").index("class_id"), Number(classId)))
      .slice()
      .sort((a, b) => String(a.due_date || "").localeCompare(String(b.due_date || "")) || a.name.localeCompare(b.name));
    const categories = (await indexGetAll(t.objectStore("categories").index("class_id"), Number(classId)))
      .slice()
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    const allGrades = await storeGetAll(t.objectStore("grades"));
    const studentIds = new Set(students.map((s) => s.id));
    const grades = allGrades.filter((g) => studentIds.has(g.student_id));
    const catById = Object.fromEntries(categories.map((c) => [c.id, c]));

    const gradeMap = {};
    for (const g of grades) gradeMap[`${g.student_id}:${g.assignment_id}`] = g;

    const rows = [];
    const overviewRows = [];
    for (const s of students) {
      const studentGrades = {};
      const gradesData = [];
      for (const a of assignments) {
        const g = gradeMap[`${s.id}:${a.id}`];
        if (!g) continue;
        const maxS = g.max_score != null ? g.max_score : a.max_score;
        studentGrades[a.id] = {
          grade_id: g.id,
          score: g.score,
          max_score: maxS,
          is_excused: g.is_excused,
          late: g.late,
          comments: g.comments || "",
          graded_at: g.graded_at || null,
          percentage: maxS > 0 ? Math.round((g.score / maxS) * 1000) / 10 : 0,
        };
        gradesData.push({
          grade: g,
          assignment: a,
          category: a.category_id != null ? catById[a.category_id] || null : null,
        });
      }
      // Include any orphan grades tied to deleted assignments? skip — only current assignments
      const avgData = global.GradeComputer.studentAverage(categories, gradesData);
      rows.push({
        student_id: s.id,
        first_name: s.first_name,
        last_name: s.last_name,
        email: s.email || "",
        name: displayName(s.first_name, s.last_name),
        grades: studentGrades,
        average: avgData.average,
        letter: avgData.letter,
        has_grades: avgData.has_grades,
      });
      overviewRows.push({
        student_id: s.id,
        name: displayName(s.first_name, s.last_name),
        average: avgData.average,
        letter: avgData.letter,
        has_grades: avgData.has_grades,
      });
    }

    return {
      class: { id: cls.id, name: cls.name, subject: cls.subject || "" },
      categories: categories.map((c) => ({ id: c.id, name: c.name, weight: c.weight })),
      assignments: assignments.map((a) => ({
        id: a.id,
        name: a.name,
        max_score: a.max_score,
        category_id: a.category_id,
        due_date: a.due_date || null,
        extra_credit: Boolean(a.extra_credit),
        created_at: a.created_at || null,
      })),
      students: rows,
      stats: global.GradeComputer.classOverview(overviewRows),
    };
  }

  function exportCsvFromGradebook(data) {
    const lines = [];
    const header = ["Student Name", "Average", "Letter Grade"];
    for (const a of data.assignments) header.push(`${a.name} (${a.max_score}pts)`);
    lines.push(header.map((h) => `"${String(h).replace(/"/g, '""')}"`).join(","));
    for (const s of data.students) {
      const row = [s.name, String(s.average), s.letter];
      for (const a of data.assignments) {
        const grade = s.grades[a.id];
        row.push(grade ? String(grade.score) : "");
      }
      lines.push(row.join(","));
    }
    return lines.join("\n");
  }

  async function exportCsv(classId, accountId) {
    const data = await getGradebook(classId, accountId);
    return exportCsvFromGradebook(data);
  }

  // ── Rewards ───────────────────────────────────────────────────────────────

  async function getRewards(classId, accountId) {
    const cls = await assertClassOwner(classId, accountId);
    const t = await tx(["students", "rewards"]);
    const students = (await indexGetAll(t.objectStore("students").index("class_id"), Number(classId)))
      .slice()
      .sort((a, b) => a.last_name.localeCompare(b.last_name) || a.first_name.localeCompare(b.first_name));
    const txs = (await indexGetAll(t.objectStore("rewards").index("class_id"), Number(classId)))
      .slice()
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)) || b.id - a.id);
    const balances = {};
    for (const item of txs) balances[item.student_id] = (balances[item.student_id] || 0) + item.points;
    const nameById = Object.fromEntries(students.map((s) => [s.id, displayName(s.first_name, s.last_name)]));
    return {
      class: { id: cls.id, name: cls.name },
      students: students.map((s) => ({
        student_id: s.id,
        name: displayName(s.first_name, s.last_name),
        balance: balances[s.id] || 0,
      })),
      transactions: txs.slice(0, 40).map((item) => ({
        id: item.id,
        student_id: item.student_id,
        student_name: nameById[item.student_id] || "Student",
        points: item.points,
        note: item.note || "",
        created_at: item.created_at,
      })),
    };
  }

  async function addReward(classId, accountId, payload) {
    await assertClassOwner(classId, accountId);
    const points = Number(payload.points);
    if (!points) throw err("Points must be greater or less than zero");
    const tRead = await tx(["students"]);
    const student = await storeGet(tRead.objectStore("students"), Number(payload.student_id));
    if (!student || student.class_id !== Number(classId)) throw err("Student must belong to this class");
    const tWrite = await tx(["rewards"], "readwrite");
    await Promise.all([
      storeAdd(tWrite.objectStore("rewards"), {
        class_id: Number(classId),
        student_id: student.id,
        points,
        note: String(payload.note || "").trim(),
        created_at: nowIso(),
      }),
      txDone(tWrite),
    ]);
    const tBal = await tx(["rewards"]);
    const all = await indexGetAll(tBal.objectStore("rewards").index("class_id"), Number(classId));
    const balance = all.filter((r) => r.student_id === student.id).reduce((s, r) => s + r.points, 0);
    return { status: "saved", balance };
  }

  // ── Goals / benchmarks ────────────────────────────────────────────────────

  function goalPayload(goal, benchmarks) {
    const benches = (benchmarks || [])
      .slice()
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || a.id - b.id)
      .map((b) => ({
        id: b.id,
        title: b.title,
        notes: b.notes || "",
        progress: b.progress,
        is_complete: b.is_complete,
        created_at: b.created_at || null,
        updated_at: b.updated_at || null,
      }));
    const progress = benches.length
      ? benches.reduce((s, b) => s + b.progress, 0) / benches.length
      : 0;
    return {
      id: goal.id,
      student_id: goal.student_id,
      title: goal.title,
      description: goal.description || "",
      target_date: goal.target_date || null,
      status: goal.status || "in_progress",
      progress: Math.round(progress * 10) / 10,
      benchmarks: benches,
      created_at: goal.created_at || null,
      updated_at: goal.updated_at || goal.created_at || null,
    };
  }

  async function getGoals(classId, accountId) {
    const cls = await assertClassOwner(classId, accountId);
    const t = await tx(["students", "goals", "benchmarks"]);
    const students = (await indexGetAll(t.objectStore("students").index("class_id"), Number(classId)))
      .slice()
      .sort((a, b) => a.last_name.localeCompare(b.last_name) || a.first_name.localeCompare(b.first_name));
    const goals = await indexGetAll(t.objectStore("goals").index("class_id"), Number(classId));
    const allBench = await storeGetAll(t.objectStore("benchmarks"));
    goals.sort((a, b) => String(a.target_date || "").localeCompare(String(b.target_date || "")) || String(b.created_at).localeCompare(String(a.created_at)));
    return {
      class: { id: cls.id, name: cls.name },
      students: students.map((s) => ({ student_id: s.id, name: displayName(s.first_name, s.last_name) })),
      goals: goals.map((g) => goalPayload(g, allBench.filter((b) => b.goal_id === g.id))),
    };
  }

  async function createGoal(classId, accountId, payload) {
    await assertClassOwner(classId, accountId);
    const tRead = await tx(["students"]);
    const student = await storeGet(tRead.objectStore("students"), Number(payload.student_id));
    if (!student || student.class_id !== Number(classId)) throw err("Student must belong to this class");
    const tWrite = await tx(["goals"], "readwrite");
    const idPromise = storeAdd(tWrite.objectStore("goals"), {
      class_id: Number(classId),
      student_id: student.id,
      title: String(payload.title || "").trim(),
      description: String(payload.description || "").trim(),
      target_date: payload.target_date || null,
      status: payload.status || "in_progress",
      created_at: nowIso(),
      updated_at: nowIso(),
    });
    await Promise.all([idPromise, txDone(tWrite)]);
    return { id: await idPromise, status: "created" };
  }

  async function updateGoal(goalId, accountId, payload) {
    const tRead = await tx(["goals", "classes", "students"]);
    const goal = await storeGet(tRead.objectStore("goals"), Number(goalId));
    if (!goal) throw err("Goal not found");
    const cls = await storeGet(tRead.objectStore("classes"), goal.class_id);
    if (!cls || cls.account_id !== Number(accountId)) throw err("Not your goal");
    const student = await storeGet(tRead.objectStore("students"), Number(payload.student_id));
    if (!student || student.class_id !== goal.class_id) throw err("Student must belong to this class");
    goal.student_id = student.id;
    goal.title = String(payload.title || "").trim();
    goal.description = String(payload.description || "").trim();
    goal.target_date = payload.target_date || null;
    goal.status = payload.status || "in_progress";
    goal.updated_at = nowIso();
    const tWrite = await tx(["goals"], "readwrite");
    await Promise.all([storePut(tWrite.objectStore("goals"), goal), txDone(tWrite)]);
    return { status: "updated" };
  }

  async function deleteGoal(goalId, accountId) {
    const tRead = await tx(["goals", "classes", "benchmarks"]);
    const goal = await storeGet(tRead.objectStore("goals"), Number(goalId));
    if (!goal) throw err("Goal not found");
    const cls = await storeGet(tRead.objectStore("classes"), goal.class_id);
    if (!cls || cls.account_id !== Number(accountId)) throw err("Not your goal");
    const benches = await indexGetAll(tRead.objectStore("benchmarks").index("goal_id"), goal.id);
    const benchIds = benches.map((b) => b.id);

    const tWrite = await tx(["goals", "benchmarks"], "readwrite");
    const deletes = benchIds.map((id) => storeDelete(tWrite.objectStore("benchmarks"), id));
    deletes.push(storeDelete(tWrite.objectStore("goals"), goal.id));
    await Promise.all([...deletes, txDone(tWrite)]);
    return { status: "deleted" };
  }

  async function createBenchmark(goalId, accountId, payload) {
    const tRead = await tx(["goals", "classes", "benchmarks"]);
    const goal = await storeGet(tRead.objectStore("goals"), Number(goalId));
    if (!goal) throw err("Goal not found");
    const cls = await storeGet(tRead.objectStore("classes"), goal.class_id);
    if (!cls || cls.account_id !== Number(accountId)) throw err("Not your goal");
    const existing = await indexGetAll(tRead.objectStore("benchmarks").index("goal_id"), goal.id);
    const isComplete = Boolean(payload.is_complete);
    goal.updated_at = nowIso();
    const tWrite = await tx(["benchmarks", "goals"], "readwrite");
    const idPromise = storeAdd(tWrite.objectStore("benchmarks"), {
      goal_id: goal.id,
      title: String(payload.title || "").trim(),
      notes: String(payload.notes || "").trim(),
      progress: isComplete ? 100 : Number(payload.progress) || 0,
      is_complete: isComplete,
      sort_order: existing.length,
      created_at: nowIso(),
      updated_at: nowIso(),
    });
    await Promise.all([idPromise, storePut(tWrite.objectStore("goals"), goal), txDone(tWrite)]);
    return { id: await idPromise, status: "created" };
  }

  async function updateBenchmark(benchmarkId, accountId, payload) {
    const tRead = await tx(["benchmarks", "goals", "classes"]);
    const bench = await storeGet(tRead.objectStore("benchmarks"), Number(benchmarkId));
    if (!bench) throw err("Benchmark not found");
    const goal = await storeGet(tRead.objectStore("goals"), bench.goal_id);
    const cls = goal ? await storeGet(tRead.objectStore("classes"), goal.class_id) : null;
    if (!cls || cls.account_id !== Number(accountId)) throw err("Not your goal");
    const isComplete = Boolean(payload.is_complete);
    bench.title = String(payload.title || "").trim();
    bench.notes = String(payload.notes || "").trim();
    bench.is_complete = isComplete;
    bench.progress = isComplete ? 100 : Number(payload.progress) || 0;
    bench.updated_at = nowIso();
    goal.updated_at = nowIso();
    const tWrite = await tx(["benchmarks", "goals"], "readwrite");
    await Promise.all([
      storePut(tWrite.objectStore("benchmarks"), bench),
      storePut(tWrite.objectStore("goals"), goal),
      txDone(tWrite),
    ]);
    return { status: "updated" };
  }

  async function deleteBenchmark(benchmarkId, accountId) {
    const tRead = await tx(["benchmarks", "goals", "classes"]);
    const bench = await storeGet(tRead.objectStore("benchmarks"), Number(benchmarkId));
    if (!bench) throw err("Benchmark not found");
    const goal = await storeGet(tRead.objectStore("goals"), bench.goal_id);
    const cls = goal ? await storeGet(tRead.objectStore("classes"), goal.class_id) : null;
    if (!cls || cls.account_id !== Number(accountId)) throw err("Not your goal");
    goal.updated_at = nowIso();
    const tWrite = await tx(["benchmarks", "goals"], "readwrite");
    await Promise.all([
      storeDelete(tWrite.objectStore("benchmarks"), bench.id),
      storePut(tWrite.objectStore("goals"), goal),
      txDone(tWrite),
    ]);
    return { status: "deleted" };
  }

  global.TB = {
    openDb,
    listAccounts,
    createAccount,
    getAccount,
    listClasses,
    createClass,
    listCategories,
    addStudentsBatch,
    updateStudent,
    deleteStudent,
    createAssignment,
    updateAssignment,
    deleteAssignment,
    upsertGrade,
    updateGrade,
    deleteGrade,
    getGradebook,
    exportCsv,
    getRewards,
    addReward,
    getGoals,
    createGoal,
    updateGoal,
    deleteGoal,
    createBenchmark,
    updateBenchmark,
    deleteBenchmark,
  };
})(typeof window !== "undefined" ? window : globalThis);
