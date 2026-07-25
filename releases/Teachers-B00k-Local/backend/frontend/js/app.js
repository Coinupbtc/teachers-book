const API = "/api";
const $ = (id) => document.getElementById(id);
const app = $("app");
const state = {
  token: localStorage.getItem("gbp_token"), teacher: null, classes: [], currentClass: null,
  gradebook: null, categories: [], search: "", assignmentFilter: "all", saving: new Set(),
  view: "classes", rewards: null
};

function headers(json = true) {
  const h = { Accept: "application/json" };
  if (json) h["Content-Type"] = "application/json";
  if (state.token) h.Authorization = `Bearer ${state.token}`;
  return h;
}
function apiErrorMessage(data, status) {
  if (typeof data === "string") return data || `Request failed (${status})`;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => {
    const field = Array.isArray(item.loc) ? item.loc.filter(part => part !== "body").join(" → ") : "";
    return field ? `${field}: ${item.msg || "Invalid value"}` : (item.msg || "Invalid value");
  }).join("; ");
  return data?.message || `Request failed (${status})`;
}
async function api(method, path, body, json = true) {
  const res = await fetch(`${API}${path}`, { method, headers: headers(json), body: body === undefined ? undefined : json ? JSON.stringify(body) : body });
  const data = res.headers.get("content-type")?.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) throw new Error(apiErrorMessage(data, res.status));
  return data;
}
const get = (path) => api("GET", path);
const post = (path, body) => api("POST", path, body);
const put = (path, body) => api("PUT", path, body);
const del = (path) => api("DELETE", path);
const esc = (value = "") => String(value).replace(/[&<>'"]/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;" })[c]);
const fmt = (n) => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
const today = () => new Date().toISOString().slice(0, 10);
function formatTimestamp(value) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—"; }

function toast(message, type = "success") {
  let box = document.querySelector(".toast-container");
  if (!box) { box = document.createElement("div"); box.className = "toast-container"; document.body.append(box); }
  const note = document.createElement("div"); note.className = `toast ${type}`; note.textContent = message; box.append(note);
  setTimeout(() => note.remove(), 3600);
}
function modal(title, contents, onReady) {
  const node = document.createElement("div"); node.className = "modal-overlay";
  node.innerHTML = `<section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button class="modal-close" aria-label="Close">×</button><h2 id="modal-title">${esc(title)}</h2>${contents}</section>`;
  document.body.append(node);
  const close = () => node.remove();
  node.addEventListener("click", e => { if (e.target === node || e.target.closest(".modal-close")) close(); });
  onReady?.(node, close);
  return node;
}
function empty(title, detail, action = "") { return `<section class="empty-state"><div class="empty-icon">▦</div><h2>${esc(title)}</h2><p>${esc(detail)}</p>${action}</section>`; }
function letterClass(letter) { return `letter-${(letter || "F")[0]}`; }

async function loadClasses() { state.classes = await get("/classes"); }
async function loadRewards() { state.rewards = await get(`/classes/${state.currentClass.id}/rewards`); }
async function loadGoals() { state.goals = await get(`/classes/${state.currentClass.id}/goals`); }
async function loadGradebook(classId = state.currentClass?.id) {
  if (classId !== state.currentClass?.id) state.assignmentFilter = "all";
  const [data, categories] = await Promise.all([get(`/classes/${classId}/gradebook`), get(`/classes/${classId}/categories`)]);
  state.currentClass = data.class;
  state.gradebook = data;
  state.categories = categories;
}
function signOut() { state.token = null; state.teacher = null; state.currentClass = null; state.gradebook = null; state.rewards = null; state.goals = null; state.view = "classes"; localStorage.removeItem("gbp_token"); render(); }
function applyTheme(theme) { document.documentElement.dataset.theme = theme; localStorage.setItem("teachers_aide_theme", theme); }
function toggleTheme() { applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"); render(); }

function loginScreen() {
  app.innerHTML = `<main class="login-page"><section class="login-card"><div class="brand-mark">✓</div><p class="eyebrow">TEACHERS B00K</p><h1>Your calm, capable gradebook.</h1><p class="login-copy">Enter scores quickly, see who needs support, and keep every class organized.</p><div class="auth-tabs"><button class="auth-tab active" data-auth="signin">Sign in</button><button class="auth-tab" data-auth="signup">Create account</button></div><div id="auth-error" class="form-error" role="alert"></div><form id="signin-form"><label>Email<input id="signin-email" class="field" type="email" autocomplete="email" placeholder="you@school.edu" required></label><label>Password<input id="signin-password" class="field" type="password" autocomplete="current-password" placeholder="Your password" required></label><button class="button primary wide">Sign in</button></form><form id="signup-form" hidden><label>Your name<input id="signup-name" class="field" autocomplete="name" placeholder="Ms. Rivera" required></label><label>Email<input id="signup-email" class="field" type="email" autocomplete="email" placeholder="you@school.edu" required></label><label>Password<input id="signup-password" class="field" type="password" autocomplete="new-password" placeholder="At least 6 characters" required></label><label>Invite code<input id="signup-invite" class="field" type="password" autocomplete="off" placeholder="Provided by your host" required></label><button class="button primary wide">Create my gradebook</button></form></section></main>`;
  document.querySelectorAll(".auth-tab").forEach(button => button.addEventListener("click", () => {
    const signup = button.dataset.auth === "signup";
    document.querySelectorAll(".auth-tab").forEach(b => b.classList.toggle("active", b === button));
    $("signin-form").hidden = signup; $("signup-form").hidden = !signup; $("auth-error").textContent = "";
  }));
  $("signin-form").addEventListener("submit", async e => {
    e.preventDefault(); await authenticate("/login", { email: $("signin-email").value.trim(), password: $("signin-password").value });
  });
  $("signup-form").addEventListener("submit", async e => {
    e.preventDefault(); const password = $("signup-password").value;
    if (password.length < 6) return showAuthError("Choose a password with at least 6 characters.");
    await authenticate("/signup", { name: $("signup-name").value.trim(), email: $("signup-email").value.trim(), password, invite_code: $("signup-invite").value.trim() });
  });
}
function showAuthError(text) { $("auth-error").textContent = text; }
async function authenticate(path, payload) {
  try { const data = await post(path, payload); state.token = data.token; state.teacher = { id: data.teacher_id, name: data.name, email: data.email }; localStorage.setItem("gbp_token", data.token); await loadClasses(); render(); }
  catch (err) { showAuthError(err.message); }
}

function shell(content) {
  const dark = document.documentElement.dataset.theme === "dark";
  return `<div class="app-shell"><header class="topbar"><button class="wordmark" data-page="classes"><span class="brand-mark small">✓</span><span>Teachers B00k</span></button><nav><button data-page="classes" class="nav-link ${state.view === "classes" ? "active" : ""}">My classes</button>${state.currentClass ? `<button data-page="gradebook" class="nav-link ${state.view === "gradebook" ? "active" : ""}">Gradebook</button><button data-page="rewards" class="nav-link ${state.view === "rewards" ? "active" : ""}">Student Rewards</button><button data-page="goals" class="nav-link ${state.view === "goals" ? "active" : ""}">Goal Tracker</button>` : ""}</nav><div class="account"><button class="theme-toggle" id="theme-toggle" aria-label="Switch to ${dark ? "light" : "dark"} mode" title="Switch to ${dark ? "light" : "dark"} mode">${dark ? "☀" : "☾"}</button><span>${esc(state.teacher?.name || "")}</span><button class="text-button" id="logout">Sign out</button></div></header><main class="content">${content}</main></div>`;
}
function classDashboard() {
  const cards = state.classes.map(cls => `<button class="class-card" data-class="${cls.id}"><div class="class-card-top"><span class="class-icon">▦</span><span class="open-arrow">→</span></div><h2>${esc(cls.name)}</h2><p>${esc(cls.subject || "No subject yet")}</p><div class="class-meta"><span>${cls.student_count} students</span><span>${cls.assignment_count} assignments</span></div></button>`).join("");
  return shell(`<section class="page-intro"><div><p class="eyebrow">YOUR TEACHING SPACE</p><h1>Good morning, ${esc((state.teacher?.name || "Teacher").split(" ")[0])}.</h1><p>Everything you need to keep grades clear and current.</p></div><button id="new-class" class="button primary">+ Add a class</button></section>${cards ? `<section class="class-grid">${cards}</section>` : empty("Set up your first class", "Start with a class roster, then Teachers B00k will keep the gradebook simple.", `<button id="new-class-empty" class="button primary">Add a class</button>`)}`);
}
function gradebookPage() {
  const data = state.gradebook;
  if (!data) return shell(`<div class="loading">Loading gradebook…</div>`);
  const assignments = data.assignments || [];
  const categories = new Map(state.categories.map(c => [c.id, c]));
  const filteredAssignments = state.assignmentFilter === "all" ? assignments : assignments.filter(a => String(a.id) === state.assignmentFilter);
  const search = state.search.trim().toLowerCase();
  const students = (data.students || []).filter(s => s.name.toLowerCase().includes(search));
  const entered = students.filter(s => s.has_grades).length;
  const support = (data.stats?.needs_support || []).length;
  const average = data.stats?.class_average || 0;
  const categoryName = a => categories.get(a.category_id)?.name || "Uncategorized";
  const assignmentOptions = assignments.map(a => `<option value="${a.id}" ${String(a.id) === state.assignmentFilter ? "selected" : ""}>${esc(a.name)} · ${fmt(a.max_score)} pts</option>`).join("");
  const grid = assignments.length ? `<div class="gradebook-shell"><div class="grid-scroll"><table class="grade-grid"><thead><tr><th class="student-column">Student</th>${filteredAssignments.map(a => `<th class="assignment-column" title="${esc(categoryName(a))}"><span>${esc(a.name)}</span><button class="assignment-menu" data-assignment-edit="${a.id}" aria-label="Edit ${esc(a.name)}">⋯</button><small>${esc(categoryName(a))} · ${fmt(a.max_score)} pts · Added ${formatTimestamp(a.created_at)}</small></th>`).join("")}<th class="average-column">Current grade</th></tr></thead><tbody>${students.length ? students.map((s, row) => `<tr><th class="student-column" scope="row"><button class="student-name-button" data-student-edit="${s.student_id}">${esc(s.name)}</button><small>${s.has_grades ? "" : "No scores yet"}</small></th>${filteredAssignments.map((a, col) => gradeCell(s, a, row, col)).join("")}<td class="average-column">${s.has_grades ? `<strong>${fmt(s.average)}%</strong><span class="letter ${letterClass(s.letter)}">${esc(s.letter)}</span>` : `<span class="muted">—</span>`}</td></tr>`).join("") : `<tr><td colspan="${filteredAssignments.length + 2}">${empty("No matching students", "Try a different name or clear the search.")}</td></tr>`}</tbody></table></div></div>` : empty("Add an assignment to begin", "Once you have an assignment, enter grades right in the grid.", `<button id="new-assignment-empty" class="button primary">+ Add assignment</button>`);
  return shell(`<section class="breadcrumb"><button data-page="classes">My classes</button><span>/</span><span>${esc(data.class.name)}</span></section><section class="page-intro gradebook-intro"><div><p class="eyebrow">${esc(data.class.subject || "GRADEBOOK")}</p><h1>${esc(data.class.name)}</h1><p>${data.stats?.student_count || 0} students · ${assignments.length} assignments</p></div><div class="action-row"><button id="export" class="button secondary">Export CSV</button><button id="add-students" class="button secondary">Add students</button><button id="new-assignment" class="button primary">+ Assignment</button></div></section><section class="snapshot"><div><span>Class average</span><strong>${entered ? `${fmt(average)}%` : "—"}</strong><small>${entered ? "Based on entered scores" : "Enter scores to see an average"}</small></div><div><span>Needs support</span><strong class="${support ? "attention" : ""}">${support}</strong><small>Students below 70%</small></div><div><span>Graded so far</span><strong>${entered}/${students.length}</strong><small>Students with at least one score</small></div><button id="view-insights" class="insight-link">View class insights →</button></section><section class="gradebook-toolbar"><label class="search"><span>⌕</span><input id="student-search" value="${esc(state.search)}" placeholder="Find a student"></label><label class="assignment-select">Showing <select id="assignment-filter"><option value="all">All assignments</option>${assignmentOptions}</select></label><p class="keyboard-tip">Tip: press Enter to move down a column. Scores save automatically.</p></section>${grid}`);
}
function gradeCell(student, assignment, row, col) {
  const grade = student.grades?.[assignment.id];
  const value = grade && !grade.is_excused ? grade.score : "";
  const flags = `${grade?.late ? " late" : ""}${grade?.is_excused ? " excused" : ""}`;
  const label = grade?.is_excused ? "Excused" : grade?.late ? "Late" : "Grade details";
  return `<td class="grade-cell${flags}"><input class="score-input" inputmode="decimal" type="number" min="0" step="0.5" max="${assignment.max_score}" aria-label="${esc(student.name)}, ${esc(assignment.name)}" data-student="${student.student_id}" data-assignment="${assignment.id}" data-row="${row}" data-col="${col}" value="${value}" placeholder="—"><button class="grade-menu" data-grade-student="${student.student_id}" data-grade-assignment="${assignment.id}" aria-label="${esc(label)}" title="${grade?.graded_at ? `Last updated ${formatTimestamp(grade.graded_at)}` : "Not graded yet"}">${grade?.is_excused ? "E" : grade?.late ? "L" : "⋯"}</button></td>`;
}
function rewardsPage() {
  const data = state.rewards;
  if (!data) return shell(`<div class="loading">Loading Student Rewards…</div>`);
  const students = data.students || [], transactions = data.transactions || [];
  return shell(`<section class="breadcrumb"><button data-page="classes">My classes</button><span>/</span><span>${esc(data.class.name)}</span><span>/</span><span>Student Rewards</span></section><section class="page-intro"><div><p class="eyebrow">CLASSROOM INCENTIVES</p><h1>Student Rewards</h1><p>Give points for great choices, and record points students spend on classroom incentives.</p></div><button class="button primary" id="reward-entry">+ Add or remove points</button></section><section class="rewards-layout"><div class="rewards-card"><div class="section-heading"><div><h2>Point balances</h2><p>Click a student to award or spend points.</p></div><strong>${students.reduce((sum, student) => sum + student.balance, 0)} total points</strong></div><div class="reward-students">${students.length ? students.map(student => `<button class="reward-student" data-reward-student="${student.student_id}"><span>${esc(student.name)}</span><strong>${student.balance}</strong><small>points</small></button>`).join("") : `<p class="muted">Add students to begin using rewards.</p>`}</div></div><div class="rewards-card"><div class="section-heading"><div><h2>Recent activity</h2><p>A clear record of every point change.</p></div></div>${transactions.length ? `<ul class="transactions">${transactions.map(item => `<li><span class="transaction-points ${item.points > 0 ? "earned" : "spent"}">${item.points > 0 ? "+" : ""}${item.points}</span><div><strong>${esc(item.student_name)}</strong><small>${esc(item.note || (item.points > 0 ? "Points earned" : "Points spent"))} · ${formatTimestamp(item.created_at)}</small></div></li>`).join("")}</ul>` : `<div class="empty-rewards">No rewards activity yet. Start by recognizing a great choice.</div>`}</div></section>`);
}
function bindRewards() { $("reward-entry")?.addEventListener("click", () => rewardModal()); document.querySelectorAll("[data-reward-student]").forEach(button => button.addEventListener("click", () => rewardModal(state.rewards.students.find(s => s.student_id === +button.dataset.rewardStudent)))); }
function rewardModal(selected = null) {
  const options = state.rewards.students.map(student => `<option value="${student.student_id}" ${selected?.student_id === student.student_id ? "selected" : ""}>${esc(student.name)} · ${student.balance} points</option>`).join("");
  modal(selected ? `Points for ${selected.name}` : "Add or remove points", `<form id="reward-form"><label>Student<select class="field" id="reward-student">${options}</select></label><div class="form-grid"><label>Action<select class="field" id="reward-action"><option value="earn">Earn points</option><option value="spend">Spend points</option></select></label><label>Points<input class="field" id="reward-points" type="number" min="1" step="1" value="1" required></label></div><label>Reason / incentive<input class="field" id="reward-note" placeholder="e.g. Helping a classmate"></label><p class="form-note">Each change is saved in the activity record, so balances stay transparent.</p><div class="modal-actions"><button type="button" class="button secondary modal-cancel">Cancel</button><button class="button primary">Save point change</button></div></form>`, (node, close) => { node.querySelector(".modal-cancel").onclick = close; node.querySelector("#reward-form").onsubmit = async e => { e.preventDefault(); const points = +$("reward-points").value * ($("reward-action").value === "spend" ? -1 : 1); try { await post(`/classes/${state.currentClass.id}/rewards`, { student_id: +$("reward-student").value, points, note: $("reward-note").value.trim() }); await loadRewards(); close(); render(); toast(points > 0 ? "Points awarded." : "Points spent recorded."); } catch (err) { toast(err.message, "error"); } }; });
}
function goalsPage() {
  const data = state.goals;
  if (!data) return shell(`<div class="loading">Loading Goal Tracker…</div>`);
  const students = new Map((data.students || []).map(student => [student.student_id, student.name]));
  const goals = data.goals || [];
  return shell(`<section class="breadcrumb"><button data-page="classes">My classes</button><span>/</span><span>${esc(data.class.name)}</span><span>/</span><span>Goal Tracker</span></section><section class="page-intro"><div><p class="eyebrow">IEP PROGRESS MONITORING</p><h1>Goal Tracker</h1><p>Keep goals, benchmarks, and progress updates in one clear, editable place.</p></div><button class="button primary" id="new-goal">+ Add IEP goal</button></section>${goals.length ? `<section class="goals-list">${goals.map(goal => `<article class="goal-card"><header><div><p class="goal-student">${esc(students.get(goal.student_id) || "Student")}</p><h2>${esc(goal.title)}</h2>${goal.description ? `<p class="goal-description">${esc(goal.description)}</p>` : ""}</div><div class="goal-actions"><button class="button secondary goal-edit" data-goal-edit="${goal.id}">Edit</button><button class="button primary benchmark-add" data-benchmark-add="${goal.id}">+ Benchmark</button></div></header><div class="goal-meta"><span>${goal.target_date ? `Target: ${esc(goal.target_date)}` : "No target date"}</span><span>Created ${formatTimestamp(goal.created_at)}</span><span>Updated ${formatTimestamp(goal.updated_at)}</span><span class="goal-status">${esc(goal.status.replace("_", " "))}</span><strong>${fmt(goal.progress)}% overall</strong></div><div class="goal-progress"><span style="width:${Math.max(0, Math.min(100, goal.progress))}%"></span></div>${goal.benchmarks.length ? `<div class="benchmark-list">${goal.benchmarks.map(benchmark => `<button class="benchmark-row" data-benchmark-edit="${benchmark.id}" data-goal-id="${goal.id}"><span class="benchmark-check ${benchmark.is_complete ? "complete" : ""}">${benchmark.is_complete ? "✓" : ""}</span><span class="benchmark-copy"><strong>${esc(benchmark.title)}</strong><small>${benchmark.notes ? `${esc(benchmark.notes)} · ` : ""}Updated ${formatTimestamp(benchmark.updated_at)}</small></span><strong class="benchmark-progress">${fmt(benchmark.progress)}%</strong><span class="row-menu">Edit →</span></button>`).join("")}</div>` : `<div class="no-benchmarks">No benchmarks yet. Add the first measurable step for this goal.</div>`}</article>`).join("")}</section>` : empty("Start tracking an IEP goal", "Add a goal for a student, then break it into measurable benchmarks and update progress as you go.", `<button class="button primary" id="new-goal-empty">+ Add IEP goal</button>`)}`);
}
function bindGoals() {
  $("new-goal")?.addEventListener("click", () => goalModal()); $("new-goal-empty")?.addEventListener("click", () => goalModal());
  document.querySelectorAll("[data-goal-edit]").forEach(button => button.addEventListener("click", () => goalModal(state.goals.goals.find(goal => goal.id === +button.dataset.goalEdit))));
  document.querySelectorAll("[data-benchmark-add]").forEach(button => button.addEventListener("click", () => benchmarkModal(state.goals.goals.find(goal => goal.id === +button.dataset.benchmarkAdd))));
  document.querySelectorAll("[data-benchmark-edit]").forEach(button => { const goal = state.goals.goals.find(item => item.id === +button.dataset.goalId); button.addEventListener("click", () => benchmarkModal(goal, goal.benchmarks.find(item => item.id === +button.dataset.benchmarkEdit))); });
}
function goalModal(goal = null) {
  const students = state.goals.students || [], editing = Boolean(goal);
  const options = students.map(student => `<option value="${student.student_id}" ${goal?.student_id === student.student_id ? "selected" : ""}>${esc(student.name)}</option>`).join("");
  modal(editing ? "Edit IEP goal" : "Add IEP goal", `<form id="goal-form"><label>Student<select class="field" id="goal-student">${options}</select></label><label>Goal statement<input class="field" id="goal-title" value="${esc(goal?.title || "")}" placeholder="e.g. Solve one-step equations with 80% accuracy" required autofocus></label><label>Notes / present level<textarea class="field" id="goal-description" rows="3" placeholder="Optional context or instructional notes">${esc(goal?.description || "")}</textarea></label><div class="form-grid"><label>Target date<input class="field" id="goal-date" type="date" value="${goal?.target_date || ""}"></label><label>Status<select class="field" id="goal-status"><option value="in_progress" ${goal?.status === "in_progress" ? "selected" : ""}>In progress</option><option value="on_track" ${goal?.status === "on_track" ? "selected" : ""}>On track</option><option value="met" ${goal?.status === "met" ? "selected" : ""}>Met</option><option value="needs_review" ${goal?.status === "needs_review" ? "selected" : ""}>Needs review</option></select></label></div><div class="modal-actions">${editing ? `<button type="button" class="button danger-outline" id="delete-goal">Delete goal</button>` : ""}<button type="button" class="button secondary modal-cancel">Cancel</button><button class="button primary">${editing ? "Save changes" : "Add goal"}</button></div></form>`, (node, close) => { node.querySelector(".modal-cancel").onclick = close; node.querySelector("#delete-goal")?.addEventListener("click", async () => { if (!confirm("Delete this IEP goal and all of its benchmarks? This cannot be undone.")) return; try { await del(`/goals/${goal.id}`); await loadGoals(); close(); render(); toast("Goal deleted."); } catch (err) { toast(err.message, "error"); } }); node.querySelector("#goal-form").onsubmit = async event => { event.preventDefault(); const payload = { student_id:+$("goal-student").value, title:$("goal-title").value.trim(), description:$("goal-description").value.trim(), target_date:$("goal-date").value || null, status:$("goal-status").value }; try { if (editing) await put(`/goals/${goal.id}`, payload); else await post(`/classes/${state.currentClass.id}/goals`, payload); await loadGoals(); close(); render(); toast(editing ? "Goal updated." : "IEP goal added."); } catch (err) { toast(err.message, "error"); } }; });
}
function benchmarkModal(goal, benchmark = null) {
  const editing = Boolean(benchmark);
  modal(editing ? "Edit benchmark" : `Add benchmark · ${goal.title}`, `<form id="benchmark-form"><label>Benchmark statement<input class="field" id="benchmark-title" value="${esc(benchmark?.title || "")}" placeholder="e.g. Identify operation in 4 of 5 problems" required autofocus></label><div class="form-grid"><label>Progress (%)<input class="field" id="benchmark-progress" type="number" min="0" max="100" step="1" value="${benchmark?.progress || 0}" required></label><label class="checkbox-label benchmark-complete"><input type="checkbox" id="benchmark-complete" ${benchmark?.is_complete ? "checked" : ""}> Benchmark met</label></div><label>Progress note<textarea class="field" id="benchmark-notes" rows="3" placeholder="Optional data point, observation, or next step">${esc(benchmark?.notes || "")}</textarea></label><div class="modal-actions">${editing ? `<button type="button" class="button danger-outline" id="delete-benchmark">Delete benchmark</button>` : ""}<button type="button" class="button secondary modal-cancel">Cancel</button><button class="button primary">${editing ? "Save changes" : "Add benchmark"}</button></div></form>`, (node, close) => { node.querySelector(".modal-cancel").onclick = close; node.querySelector("#delete-benchmark")?.addEventListener("click", async () => { if (!confirm("Delete this benchmark? This cannot be undone.")) return; try { await del(`/benchmarks/${benchmark.id}`); await loadGoals(); close(); render(); toast("Benchmark deleted."); } catch (err) { toast(err.message, "error"); } }); node.querySelector("#benchmark-form").onsubmit = async event => { event.preventDefault(); const payload = { title:$("benchmark-title").value.trim(), progress:+$("benchmark-progress").value, is_complete:$("benchmark-complete").checked, notes:$("benchmark-notes").value.trim() }; try { if (editing) await put(`/benchmarks/${benchmark.id}`, payload); else await post(`/goals/${goal.id}/benchmarks`, payload); await loadGoals(); close(); render(); toast(editing ? "Benchmark updated." : "Benchmark added."); } catch (err) { toast(err.message, "error"); } }; });
}
function render() {
  if (!state.token) return loginScreen();
  app.innerHTML = state.view === "rewards" ? rewardsPage() : state.view === "goals" ? goalsPage() : state.currentClass ? gradebookPage() : classDashboard();
  bindShell();
  if (state.view === "rewards") bindRewards(); else if (state.view === "goals") bindGoals(); else if (state.currentClass) bindGradebook(); else bindDashboard();
}
function bindShell() {
  document.querySelectorAll("[data-page]").forEach(btn => btn.addEventListener("click", async () => {
    const page = btn.dataset.page;
    if (page === "classes") { state.currentClass = null; state.gradebook = null; state.rewards = null; state.goals = null; state.search = ""; state.view = "classes"; await loadClasses(); render(); }
    if (page === "gradebook" && state.currentClass) { state.view = "gradebook"; await loadGradebook(); render(); }
    if (page === "rewards" && state.currentClass) { state.view = "rewards"; await loadRewards(); render(); }
    if (page === "goals" && state.currentClass) { state.view = "goals"; await loadGoals(); render(); }
  }));
  $("logout")?.addEventListener("click", signOut); $("theme-toggle")?.addEventListener("click", toggleTheme);
}
function bindDashboard() {
  document.querySelectorAll("[data-class]").forEach(card => card.addEventListener("click", async () => { state.view = "gradebook"; await loadGradebook(card.dataset.class); render(); }));
  $("new-class")?.addEventListener("click", newClassModal); $("new-class-empty")?.addEventListener("click", newClassModal);
}
function bindGradebook() {
  $("new-assignment")?.addEventListener("click", assignmentModal); $("new-assignment-empty")?.addEventListener("click", assignmentModal);
  $("add-students")?.addEventListener("click", studentsModal); $("export")?.addEventListener("click", exportCsv); $("view-insights")?.addEventListener("click", insightsModal);
  $("student-search")?.addEventListener("input", e => { state.search = e.target.value; render(); $("student-search")?.focus(); });
  $("assignment-filter")?.addEventListener("change", e => { state.assignmentFilter = e.target.value; render(); });
  document.querySelectorAll(".score-input").forEach(input => {
    let timer;
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => saveGridGrade(input), 650); });
    input.addEventListener("blur", () => { clearTimeout(timer); saveGridGrade(input); });
    input.addEventListener("keydown", e => {
      if (e.key === "Enter") { e.preventDefault(); clearTimeout(timer); saveGridGrade(input).then(() => focusNextRow(input)); }
      if (e.key === "Escape") { input.blur(); }
    });
  });
  document.querySelectorAll(".grade-menu").forEach(button => button.addEventListener("click", () => gradeModal(+button.dataset.gradeStudent, +button.dataset.gradeAssignment)));
  document.querySelectorAll("[data-assignment-edit]").forEach(button => button.addEventListener("click", () => assignmentModal(findAssignment(+button.dataset.assignmentEdit))));
  document.querySelectorAll("[data-student-edit]").forEach(button => button.addEventListener("click", () => studentModal(findStudent(+button.dataset.studentEdit))));
}
function findStudent(id) { return state.gradebook.students.find(s => s.student_id === id); }
function findAssignment(id) { return state.gradebook.assignments.find(a => a.id === id); }
async function saveGridGrade(input) {
  const studentId = +input.dataset.student, assignmentId = +input.dataset.assignment, key = `${studentId}:${assignmentId}`;
  if (state.saving.has(key)) return;
  const student = findStudent(studentId), existing = student?.grades?.[assignmentId], raw = input.value.trim();
  if (!raw && !existing) return;
  if (raw && Number.isNaN(Number(raw))) return;
  const score = Number(raw);
  if (score < 0) { toast("Scores cannot be negative.", "error"); return; }
  if (raw && existing && score === existing.score && !existing.is_excused) return;
  state.saving.add(key); input.classList.add("saving");
  try {
    if (!raw && existing) await del(`/grades/${existing.grade_id}`);
    else if (existing) await put(`/grades/${existing.grade_id}`, { score, is_excused: false, late: existing.late, comments: existing.comments || "" });
    else await post(`/classes/${state.currentClass.id}/grades`, { student_id: studentId, assignment_id: assignmentId, score });
    await loadGradebook(); render();
  } catch (err) { input.classList.remove("saving"); toast(`Could not save score: ${err.message}`, "error"); }
  finally { state.saving.delete(key); }
}
function focusNextRow(input) {
  const row = +input.dataset.row + 1, col = input.dataset.col;
  const next = document.querySelector(`.score-input[data-row="${row}"][data-col="${col}"]`);
  if (next) { next.focus(); next.select(); }
}
function newClassModal() {
  modal("Add a class", `<form id="class-form"><div class="form-grid"><label>Class name<input class="field" id="class-name" placeholder="e.g. Algebra I" required autofocus></label><label>Subject<input class="field" id="class-subject" placeholder="e.g. Mathematics"></label></div><label>Grade level <input class="field" id="class-level" placeholder="e.g. 9th grade"></label><p class="form-note">We’ll set up useful categories for you: Tests, Quizzes, Homework, Classwork, and Participation.</p><div class="modal-actions"><button type="button" class="button secondary modal-cancel">Cancel</button><button class="button primary">Create class</button></div></form>`, (node, close) => {
    node.querySelector(".modal-cancel").onclick = close; node.querySelector("#class-form").onsubmit = async e => { e.preventDefault(); try { await post("/classes", { name: $("class-name").value.trim(), subject: $("class-subject").value.trim(), grade_level: $("class-level").value.trim() }); await loadClasses(); close(); render(); toast("Class created. Your gradebook is ready."); } catch (err) { toast(err.message, "error"); } };
  });
}
function assignmentModal(assignment = null) {
  const options = state.categories.map(c => `<option value="${c.id}" ${assignment?.category_id === c.id ? "selected" : ""}>${esc(c.name)} · ${fmt(c.weight_pct)}%</option>`).join("");
  const editing = Boolean(assignment);
  modal(editing ? "Edit assignment" : "Add an assignment", `<form id="assignment-form"><label>Assignment name<input class="field" id="assignment-name" value="${esc(assignment?.name || "")}" placeholder="e.g. Unit 2 quiz" required autofocus></label><div class="form-grid"><label>Points possible<input class="field" id="assignment-points" type="number" min="0.5" step="0.5" value="${assignment?.max_score || 100}" required></label><label>Due date<input class="field" id="assignment-date" type="date" value="${assignment?.due_date || today()}"></label></div><label>Category<select class="field" id="assignment-category"><option value="">Uncategorized</option>${options}</select></label><label class="checkbox-label"><input type="checkbox" id="assignment-extra" ${assignment?.extra_credit ? "checked" : ""}> This is extra credit</label><div class="modal-actions">${editing ? `<button type="button" id="delete-assignment" class="button danger-outline">Delete assignment</button>` : ""}<button type="button" class="button secondary modal-cancel">Cancel</button><button class="button primary">${editing ? "Save changes" : "Add assignment"}</button></div></form>`, (node, close) => {
    node.querySelector(".modal-cancel").onclick = close;
    node.querySelector("#delete-assignment")?.addEventListener("click", async () => { if (!confirm(`Delete “${assignment.name}” and all of its grades? This cannot be undone.`)) return; try { await del(`/assignments/${assignment.id}`); await loadGradebook(); close(); render(); toast("Assignment deleted."); } catch (err) { toast(err.message, "error"); } });
    node.querySelector("#assignment-form").onsubmit = async e => { e.preventDefault(); const classId = Number(state.currentClass?.id); const name = $("assignment-name").value.trim(); const maxScore = Number($("assignment-points").value); const dueDate = $("assignment-date").value; const category = $("assignment-category").value; if (!Number.isInteger(classId) || classId <= 0) return toast("Choose a class before adding an assignment.", "error"); if (!name) return toast("Enter an assignment name.", "error"); if (!Number.isFinite(maxScore) || maxScore <= 0) return toast("Points possible must be greater than zero.", "error"); if (dueDate && !/^\d{4}-\d{2}-\d{2}$/.test(dueDate)) return toast("Choose a valid due date.", "error"); const payload = { name, max_score: maxScore, category_id: category ? Number(category) : null, extra_credit: $("assignment-extra").checked }; if (dueDate) payload.due_date = dueDate; try { if (editing) await put(`/assignments/${assignment.id}`, payload); else await post(`/classes/${classId}/assignments`, payload); await loadGradebook(classId); close(); render(); toast(editing ? "Assignment updated." : "Assignment added. Start entering scores when you’re ready."); } catch (err) { toast(err.message || "Could not save the assignment.", "error"); } };
  });
}
function studentsModal() {
  modal("Add students", `<form id="students-form"><label>Student names<textarea class="field" id="student-names" rows="7" placeholder="Avery Brooks\nJordan Chen\nSam Patel" required autofocus></textarea></label><p class="form-note">One student per line. Enter names as First Last; we’ll sort the roster by last name.</p><div class="modal-actions"><button type="button" class="button secondary modal-cancel">Cancel</button><button class="button primary">Add students</button></div></form>`, (node, close) => {
    node.querySelector(".modal-cancel").onclick = close; node.querySelector("#students-form").onsubmit = async e => { e.preventDefault(); const rows = $("student-names").value.split("\n").map(v => v.trim()).filter(Boolean).map(name => { const parts = name.split(/\s+/); return { first_name: parts.shift(), last_name: parts.join(" ") || "Student" }; }); try { const form = new URLSearchParams({ students_json: JSON.stringify(rows) }); await api("POST", `/classes/${state.currentClass.id}/students/batch`, form, false); await loadGradebook(); close(); render(); toast(`${rows.length} student${rows.length === 1 ? "" : "s"} added to the roster.`); } catch (err) { toast(err.message, "error"); } };
  });
}
function studentModal(student) {
  modal(`Edit ${student.name}`, `<form id="student-form"><div class="form-grid"><label>First name<input class="field" id="student-first" value="${esc(student.first_name || student.name.split(" ")[0])}" required autofocus></label><label>Last name<input class="field" id="student-last" value="${esc(student.last_name || student.name.split(" ").slice(1).join(" "))}" required></label></div><label>Email (optional)<input class="field" id="student-email" value="${esc(student.email || "")}" type="email"></label><div class="modal-actions"><button type="button" id="delete-student" class="button danger-outline">Remove student</button><button type="button" class="button secondary modal-cancel">Cancel</button><button class="button primary">Save changes</button></div></form>`, (node, close) => {
    node.querySelector(".modal-cancel").onclick = close;
    node.querySelector("#delete-student").onclick = async () => { if (!confirm(`Remove ${student.name} and their grades from this class? This cannot be undone.`)) return; try { await del(`/students/${student.student_id}`); await loadGradebook(); close(); render(); toast("Student removed from this class."); } catch (err) { toast(err.message, "error"); } };
    node.querySelector("#student-form").onsubmit = async e => { e.preventDefault(); try { await put(`/students/${student.student_id}`, { first_name: $("student-first").value.trim(), last_name: $("student-last").value.trim(), email: $("student-email").value.trim() }); await loadGradebook(); close(); render(); toast("Student updated."); } catch (err) { toast(err.message, "error"); } };
  });
}
function gradeModal(studentId, assignmentId) {
  const student = findStudent(studentId), assignment = findAssignment(assignmentId), existing = student.grades?.[assignmentId];
  const timestamp = existing?.graded_at ? `<p class="form-note">Last updated ${formatTimestamp(existing.graded_at)}</p>` : `<p class="form-note">Not graded yet</p>`;
  modal(`${student.name} · ${assignment.name}`, `<form id="grade-form">${timestamp}<div class="score-summary"><label>Score<input class="field" id="detail-score" type="number" min="0" step="0.5" value="${existing && !existing.is_excused ? existing.score : ""}" placeholder="Not graded"></label><span>out of ${fmt(assignment.max_score)} points</span></div><div class="form-grid"><label class="checkbox-label"><input id="detail-excused" type="checkbox" ${existing?.is_excused ? "checked" : ""}> Excused</label><label class="checkbox-label"><input id="detail-late" type="checkbox" ${existing?.late ? "checked" : ""}> Submitted late</label></div><label>Private note / feedback<textarea class="field" id="detail-comments" rows="3" placeholder="Optional note for your records">${esc(existing?.comments || "")}</textarea></label><div class="modal-actions">${existing ? `<button type="button" id="clear-grade" class="button danger-outline">Clear score</button>` : ""}<button type="button" class="button secondary modal-cancel">Cancel</button><button class="button primary">Save grade</button></div></form>`, (node, close) => {
    node.querySelector(".modal-cancel").onclick = close; node.querySelector("#clear-grade")?.addEventListener("click", async () => { if (!confirm("Clear this score?")) return; try { await del(`/grades/${existing.grade_id}`); await loadGradebook(); close(); render(); toast("Score cleared."); } catch (err) { toast(err.message, "error"); } });
    node.querySelector("#grade-form").onsubmit = async e => { e.preventDefault(); const scoreText = $("detail-score").value.trim(), excused = $("detail-excused").checked; if (!scoreText && !excused) return toast("Enter a score or mark the student excused.", "error"); const payload = { student_id: studentId, assignment_id: assignmentId, score: scoreText ? +scoreText : 0, is_excused: excused, late: $("detail-late").checked, comments: $("detail-comments").value.trim() }; try { if (existing) await put(`/grades/${existing.grade_id}`, payload); else await post(`/classes/${state.currentClass.id}/grades`, payload); await loadGradebook(); close(); render(); toast(excused ? "Marked excused." : "Grade saved."); } catch (err) { toast(err.message, "error"); } };
  });
}
function insightsModal() {
  const stats = state.gradebook.stats || {}, support = stats.needs_support || [], top = stats.top_performer;
  modal("Class insights", `<div class="insights"><div class="insight-stat"><span>Class average</span><strong>${fmt(stats.class_average)}%</strong></div><div class="insight-stat"><span>Top current grade</span><strong>${top ? `${esc(top.name)} · ${fmt(top.average)}%` : "—"}</strong></div><h3>Students who may need a check-in</h3>${support.length ? `<ul>${support.map(s => `<li><span>${esc(s.name)}</span><strong>${fmt(s.average)}%</strong></li>`).join("")}</ul>` : `<p class="positive-note">No students are currently below 70%. Nice work.</p>`}</div>`, () => {});
}
async function exportCsv() {
  try { const csv = await get(`/classes/${state.currentClass.id}/export/csv`); const blob = new Blob([csv], { type: "text/csv" }), link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${state.currentClass.name.replace(/\W+/g, "_")}_gradebook.csv` }); link.click(); URL.revokeObjectURL(link.href); toast("Gradebook exported as CSV."); } catch (err) { toast(err.message, "error"); }
}
async function boot() {
  applyTheme(localStorage.getItem("teachers_aide_theme") || "light");
  if (!state.token) return render();
  try { state.teacher = await get("/me"); await loadClasses(); render(); } catch { signOut(); }
}
document.addEventListener("DOMContentLoaded", boot);
