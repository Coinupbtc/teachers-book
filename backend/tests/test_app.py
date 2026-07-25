"""Tests for GradeBook Pro — auth, models, routes, grade computer"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import date

from app.models import Base, Teacher, Class, Student, Category, Assignment, Grade, GradeComputer, get_db
from app.main import create_app

# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite:///./test_gradebook.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh tables for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Get a test database session."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """FastAPI test client with overridden DB dependency."""
    app = create_app()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def teacher(db):
    t = Teacher(email="teacher@test.com", name="Test Teacher")
    t.set_password("secret123")
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def auth_headers(client, teacher):
    """Login and get auth headers."""
    r = client.post("/api/login", json={"email": "teacher@test.com", "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def class_with_data(db, teacher):
    """Set up a class with students, categories, assignments, and grades."""
    cls = Class(teacher_id=teacher.id, name="Algebra I", subject="Math")
    db.add(cls)
    db.flush()

    cats = []
    for name, weight in [("Tests", 0.35), ("Homework", 0.20), ("Quizzes", 0.20)]:
        c = Category(class_id=cls.id, name=name, weight=weight, sort_order=len(cats))
        db.add(c)
        cats.append(c)
    db.flush()

    students = []
    for fn, ln in [("Alice", "Johnson"), ("Bob", "Smith"), ("Carol", "Williams")]:
        s = Student(class_id=cls.id, first_name=fn, last_name=ln)
        db.add(s)
        students.append(s)
    db.flush()

    a1 = Assignment(class_id=cls.id, name="Midterm", max_score=100, category_id=cats[0].id)
    a2 = Assignment(class_id=cls.id, name="HW1", max_score=20, category_id=cats[1].id)
    db.add(a1)
    db.add(a2)
    db.flush()

    # Grades: Alice
    db.add(Grade(student_id=students[0].id, assignment_id=a1.id, score=88.0))
    db.add(Grade(student_id=students[0].id, assignment_id=a2.id, score=18.0))
    # Bob
    db.add(Grade(student_id=students[1].id, assignment_id=a1.id, score=72.0))
    db.add(Grade(student_id=students[1].id, assignment_id=a2.id, score=15.0))
    # Carol
    db.add(Grade(student_id=students[2].id, assignment_id=a1.id, score=95.0))
    db.add(Grade(student_id=students[2].id, assignment_id=a2.id, score=20.0))
    db.commit()

    return cls, cats, students, [a1, a2]


# ═══════════════════════════════════════════════
# Auth Tests
# ═══════════════════════════════════════════════

def test_signup(client):
    r = client.post("/api/signup", json={"email": "new@test.com", "name": "New", "password": "pass"})
    assert r.status_code == 200
    data = r.json()
    assert data["teacher_id"] > 0
    assert data["name"] == "New"
    assert "token" in data


def test_signup_duplicate_email(client, teacher):
    r = client.post("/api/signup", json={"email": "teacher@test.com", "name": "Dup", "password": "pass"})
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_login(client, teacher):
    r = client.post("/api/login", json={"email": "teacher@test.com", "password": "secret123"})
    assert r.status_code == 200
    data = r.json()
    assert data["teacher_id"] == teacher.id
    assert "token" in data


def test_login_bad_password(client, teacher):
    r = client.post("/api/login", json={"email": "teacher@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_authenticated(client, auth_headers):
    r = client.get("/api/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "teacher@test.com"


def test_me_unauthenticated(client):
    r = client.get("/api/me")
    assert r.status_code == 401


def test_token_works_across_requests(client, teacher):
    """Verify token reuse (not in-memory session)."""
    r1 = client.post("/api/login", json={"email": "teacher@test.com", "password": "secret123"})
    token = r1.json()["token"]

    r2 = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200


# ═══════════════════════════════════════════════
# Class Tests
# ═══════════════════════════════════════════════

def test_create_class(client, auth_headers):
    r = client.post("/api/classes", json={"name": "Biology", "subject": "Science"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Biology"


def test_list_classes(client, auth_headers):
    r = client.post("/api/classes", json={"name": "Physics"}, headers=auth_headers)
    r = client.get("/api/classes", headers=auth_headers)
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Physics"


def test_list_classes_empty(client, auth_headers):
    r = client.get("/api/classes", headers=auth_headers)
    assert r.json() == []


# ═══════════════════════════════════════════════
# Student Tests
# ═══════════════════════════════════════════════

def test_add_student(client, auth_headers):
    # Create class first
    r = client.post("/api/classes", json={"name": "Chem"}, headers=auth_headers)
    class_id = r.json()["id"]

    r = client.post(f"/api/classes/{class_id}/students",
                    json={"first_name": "John", "last_name": "Doe"},
                    headers=auth_headers)
    assert r.status_code == 200
    assert "John Doe" in r.json()["display_name"]


def test_add_student_nonexistent_class(client, auth_headers):
    r = client.post("/api/classes/999/students",
                    json={"first_name": "John", "last_name": "Doe"},
                    headers=auth_headers)
    assert r.status_code == 404


def test_batch_add_students(client, auth_headers):
    r = client.post("/api/classes", json={"name": "Hist"}, headers=auth_headers)
    class_id = r.json()["id"]

    payload = [{"first_name": "A", "last_name": "X"}, {"first_name": "B", "last_name": "Y"}]
    r = client.post(f"/api/classes/{class_id}/students/batch",
                    data={"students_json": str(payload).replace("'", '"')},
                    headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["added"] == 2


# ═══════════════════════════════════════════════
# Grade Computation Tests
# ═══════════════════════════════════════════════

class TestGradeComputer:
    def test_simple_average(self, db, teacher):
        cls = Class(teacher_id=teacher.id, name="Test")
        db.add(cls)
        db.flush()

        s = Student(class_id=cls.id, first_name="Test", last_name="Student")
        db.add(s)
        db.flush()

        # No categories = simple average
        for i, (score, max_s) in enumerate([(80, 100), (90, 100), (70, 100)]):
            a = Assignment(class_id=cls.id, name=f"Test {i}", max_score=max_s)
            db.add(a)
            db.flush()
            db.add(Grade(student_id=s.id, assignment_id=a.id, score=score))
        db.commit()

        computer = GradeComputer(db)
        result = computer.student_average(s.id, cls.id)
        assert result["average"] == 80.0
        assert result["letter"] == "B-"

    def test_weighted_average(self, db, teacher):
        cls = Class(teacher_id=teacher.id, name="Weighted")
        db.add(cls)
        db.flush()

        tests_cat = Category(class_id=cls.id, name="Tests", weight=0.40)
        hw_cat = Category(class_id=cls.id, name="Homework", weight=0.60)
        db.add(tests_cat)
        db.add(hw_cat)
        db.flush()

        s = Student(class_id=cls.id, first_name="S", last_name="T")
        db.add(s)
        db.flush()

        # Test: 90% weighted 0.40 → 36
        # HW: 80% weighted 0.60 → 48
        # Total: 84%
        a1 = Assignment(class_id=cls.id, name="Exam", max_score=100, category_id=tests_cat.id)
        a2 = Assignment(class_id=cls.id, name="HW Set", max_score=100, category_id=hw_cat.id)
        db.add(a1)
        db.add(a2)
        db.flush()
        db.add(Grade(student_id=s.id, assignment_id=a1.id, score=90))
        db.add(Grade(student_id=s.id, assignment_id=a2.id, score=80))
        db.commit()

        computer = GradeComputer(db)
        result = computer.student_average(s.id, cls.id)
        assert result["average"] == 84.0
        assert result["letter"] == "B"

    def test_drop_lowest(self, db, teacher):
        cls = Class(teacher_id=teacher.id, name="Drop")
        db.add(cls)
        db.flush()

        cat = Category(class_id=cls.id, name="Homeworks", weight=1.0, drop_lowest=1)
        db.add(cat)
        db.flush()

        s = Student(class_id=cls.id, first_name="S", last_name="T")
        db.add(s)
        db.flush()

        a1 = Assignment(class_id=cls.id, name="HW1", max_score=100, category_id=cat.id)
        a2 = Assignment(class_id=cls.id, name="HW2", max_score=100, category_id=cat.id)
        a3 = Assignment(class_id=cls.id, name="HW3", max_score=100, category_id=cat.id)
        db.add_all([a1, a2, a3])
        db.flush()

        db.add(Grade(student_id=s.id, assignment_id=a1.id, score=50))  # dropped
        db.add(Grade(student_id=s.id, assignment_id=a2.id, score=100))
        db.add(Grade(student_id=s.id, assignment_id=a3.id, score=90))
        db.commit()

        computer = GradeComputer(db)
        result = computer.student_average(s.id, cls.id)
        # Without drop: (50+100+90)/3 = 80%
        # With drop 1:  (100+90)/2 = 95%
        assert result["average"] == 95.0

    def test_excused_grades_excluded(self, db, teacher):
        cls = Class(teacher_id=teacher.id, name="Excused")
        db.add(cls)
        db.flush()
        s = Student(class_id=cls.id, first_name="S", last_name="T")
        db.add(s)
        db.flush()
        a1 = Assignment(class_id=cls.id, name="A1", max_score=100)
        a2 = Assignment(class_id=cls.id, name="A2", max_score=100)
        db.add_all([a1, a2])
        db.flush()
        db.add(Grade(student_id=s.id, assignment_id=a1.id, score=100.0))
        db.add(Grade(student_id=s.id, assignment_id=a2.id, score=0.0, is_excused=True))
        db.commit()

        computer = GradeComputer(db)
        result = computer.student_average(s.id, cls.id)
        # Only A1 counts: 100%
        assert result["average"] == 100.0

    def test_letter_grades(self):
        computer = GradeComputer(None)  # type: ignore
        # Don't use instance method for static test
        from app.models import GradeComputer as GC
        gc = GC.__new__(GC)
        assert gc._to_letter(95) == "A"
        assert gc._to_letter(91) == "A-"
        assert gc._to_letter(88) == "B+"
        assert gc._to_letter(84) == "B"
        assert gc._to_letter(81) == "B-"
        assert gc._to_letter(77) == "C+"
        assert gc._to_letter(73) == "C"
        assert gc._to_letter(70) == "C-"
        assert gc._to_letter(67) == "D+"
        assert gc._to_letter(62) == "D"
        assert gc._to_letter(59) == "F"

    def test_assignment_stats(self, db, teacher):
        cls = Class(teacher_id=teacher.id, name="Stats")
        db.add(cls)
        db.flush()

        a = Assignment(class_id=cls.id, name="Test", max_score=100)
        db.add(a)
        db.flush()

        scores = [88, 72, 95, 64, 91]
        for i, score in enumerate(scores):
            s = Student(class_id=cls.id, first_name=f"S{i}", last_name=f"T{i}")
            db.add(s)
            db.flush()
            db.add(Grade(student_id=s.id, assignment_id=a.id, score=score))
        db.commit()

        computer = GradeComputer(db)
        stats = computer.assignment_stats(a.id)
        assert stats["count"] == 5
        assert stats["min"] == 64
        assert stats["max"] == 95
        assert stats["average"] == 82.0  # (88+72+95+64+91)/5
        assert stats["median"] == 88

    def test_class_overview(self, db, teacher):
        cls = Class(teacher_id=teacher.id, name="Overview")
        db.add(cls)
        db.flush()
        a = Assignment(class_id=cls.id, name="Exam", max_score=100)
        db.add(a)
        db.flush()

        for fn, ln, score in [("A", "H", 95), ("B", "M", 75), ("C", "L", 55)]:
            s = Student(class_id=cls.id, first_name=fn, last_name=ln)
            db.add(s)
            db.flush()
            db.add(Grade(student_id=s.id, assignment_id=a.id, score=score))
        db.commit()

        computer = GradeComputer(db)
        overview = computer.class_overview(cls.id)
        assert overview["student_count"] == 3
        assert overview["class_average"] == 75.0
        assert overview["top_performer"]["average"] == 95.0
        assert len(overview["needs_support"]) == 1  # 55 < 70
        assert overview["grade_distribution"]["A"] == 1
        assert overview["grade_distribution"]["F"] == 1  # 55 = F (below 60)
        assert overview["grade_distribution"]["C"] == 1  # 75 = C


# ═══════════════════════════════════════════════
# Gradebook API Tests
# ═══════════════════════════════════════════════

def test_gradebook_view(client, auth_headers, db):
    # Use manual setup for full API test
    r = client.post("/api/classes", json={"name": "GB Test"}, headers=auth_headers)
    class_id = r.json()["id"]

    payload = [{"first_name": "Alice", "last_name": "J"}, {"first_name": "Bob", "last_name": "S"}]
    r = client.post(f"/api/classes/{class_id}/students/batch",
                    data={"students_json": str(payload).replace("'", '"')},
                    headers=auth_headers)
    assert r.json()["added"] == 2

    r = client.get(f"/api/classes/{class_id}/gradebook", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["class"]["name"] == "GB Test"
    assert len(data["students"]) == 2
    assert data["stats"]["student_count"] == 2


def test_analytics(client, auth_headers):
    r = client.post("/api/classes", json={"name": "Analytics Class"}, headers=auth_headers)
    class_id = r.json()["id"]

    r = client.get(f"/api/classes/{class_id}/analytics", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["overview"]["student_count"] == 0


def test_csv_export(client, auth_headers):
    r = client.post("/api/classes", json={"name": "CSV Export"}, headers=auth_headers)
    class_id = r.json()["id"]

    r = client.get(f"/api/classes/{class_id}/export/csv", headers=auth_headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "Student Name" in r.text
