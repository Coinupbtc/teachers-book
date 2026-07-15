"""GradeBook Pro — Database Models (v2)

Fixed: added proper __init__.py, no duplicate imports, all relationships clean.
"""
import os
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text, Boolean,
    DateTime, Date, ForeignKey, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import timedelta

from app.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    school = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    classes = relationship("Class", back_populates="teacher", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.hashed_password = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)

    def make_token(self) -> str:
        """Create a JWT for this teacher."""
        from datetime import timezone
        payload = {
            "sub": str(self.id),
            "email": self.email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Optional[int]:
        """Verify JWT and return teacher_id, or None."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return int(payload["sub"])
        except (JWTError, ValueError, KeyError):
            return None


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    subject = Column(String(255), default="")
    grade_level = Column(String(50), default="")
    semester = Column(String(50), default="Fall 2026")
    school_year = Column(String(50), default="2026-2027")
    created_at = Column(DateTime, default=datetime.utcnow)

    teacher = relationship("Teacher", back_populates="classes")
    students = relationship("Student", back_populates="class_", cascade="all, delete-orphan",
                            order_by="Student.last_name, Student.first_name")
    assignments = relationship("Assignment", back_populates="class_", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="class_", cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), default="")
    student_id = Column(String(50), default="")
    notes = Column(Text, default="")
    photo_url = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    class_ = relationship("Class", back_populates="students")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.last_name}, {self.first_name}"

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    name = Column(String(100), nullable=False)
    weight = Column(Float, default=1.0)
    drop_lowest = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)

    class_ = relationship("Class", back_populates="categories")
    assignments = relationship("Assignment", back_populates="category")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    max_score = Column(Float, nullable=False, default=100.0)
    due_date = Column(Date, nullable=True)
    assignment_type = Column(String(50), default="points")
    rubric_id = Column(Integer, ForeignKey("rubrics.id"), nullable=True)
    extra_credit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    class_ = relationship("Class", back_populates="assignments")
    category = relationship("Category", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan")
    rubric = relationship("Rubric", backref="assignments")


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("student_id", "assignment_id", name="uq_student_assignment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    max_score = Column(Float, nullable=True)
    is_excused = Column(Boolean, default=False)
    late = Column(Boolean, default=False)
    comments = Column(Text, default="")
    graded_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="grades")
    assignment = relationship("Assignment", back_populates="grades")


class Rubric(Base):
    __tablename__ = "rubrics"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    criteria = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RubricScore(Base):
    __tablename__ = "rubric_scores"
    __table_args__ = (
        UniqueConstraint("student_id", "assignment_id", "criterion_index", name="uq_rubric_criterion"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    criterion_index = Column(Integer, nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    comments = Column(Text, default="")


class IEPGoal(Base):
    __tablename__ = "iep_goals"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    target_date = Column(Date, nullable=True)
    status = Column(String(30), default="in_progress", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    benchmarks = relationship("GoalBenchmark", back_populates="goal", cascade="all, delete-orphan", order_by="GoalBenchmark.sort_order, GoalBenchmark.id")


class GoalBenchmark(Base):
    __tablename__ = "goal_benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("iep_goals.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    notes = Column(Text, default="")
    progress = Column(Float, default=0.0, nullable=False)
    is_complete = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    goal = relationship("IEPGoal", back_populates="benchmarks")


class RewardTransaction(Base):
    """An auditable classroom-points entry for a student."""
    __tablename__ = "reward_transactions"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    points = Column(Integer, nullable=False)
    note = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String(20), default="present")
    notes = Column(Text, default="")

    __table_args__ = (
        UniqueConstraint("student_id", "class_id", "date", name="uq_attendance"),
    )


# ─── Grade Computer (unchanged from v1 — already solid) ──────────────────────

class GradeComputer:
    """Handles all grade calculations with eager-loaded data."""

    def __init__(self, db: Session):
        self.db = db

    def student_average(self, student_id: int, class_id: int) -> dict:
        categories = self.db.query(Category).filter(
            Category.class_id == class_id
        ).order_by(Category.sort_order).all()

        grades_data = (
            self.db.query(Grade, Assignment, Category)
            .join(Assignment, Grade.assignment_id == Assignment.id)
            .join(Category, Assignment.category_id == Category.id, isouter=True)
            .filter(Grade.student_id == student_id)
            .filter(Assignment.class_id == class_id)
            .all()
        )

        if not categories:
            result = self._simple_average(grades_data)
        else:
            result = self._weighted_average(grades_data, categories)
        result["has_grades"] = any(not grade.is_excused for grade, _, _ in grades_data)
        return result

    def _simple_average(self, grades_data: list) -> dict:
        scores = []
        total_points = 0.0
        total_possible = 0.0
        for g, a, _ in grades_data:
            if g.is_excused:
                continue
            max_s = g.max_score if g.max_score else a.max_score
            if max_s > 0:
                scores.append((g.score / max_s) * 100)
            total_points += g.score
            total_possible += max_s
        avg = sum(scores) / len(scores) if scores else 0.0
        return {
            "average": round(avg, 1),
            "letter": self._to_letter(avg),
            "total_points": round(total_points, 1),
            "total_possible": round(total_possible, 1),
            "assignments_graded": len(scores),
        }

    def _weighted_average(self, grades_data: list, categories: list) -> dict:
        cat_grades = {c.id: [] for c in categories}
        other_grades = []
        for g, a, c in grades_data:
            if g.is_excused:
                continue
            if c and c.id in cat_grades:
                cat_grades[c.id].append((g, a))
            else:
                other_grades.append((g, a))

        total_weight = 0.0
        weighted_sum = 0.0
        by_category = {}

        for cat in categories:
            items = cat_grades[cat.id]
            if not items:
                by_category[cat.name] = 0.0
                continue
            sorted_items = sorted(
                items,
                key=lambda x: x[0].score / (x[0].max_score or x[1].max_score or 1)
            )
            if cat.drop_lowest > 0:
                sorted_items = sorted_items[cat.drop_lowest:]
            scores = []
            for g, a in sorted_items:
                max_s = g.max_score if g.max_score else a.max_score
                if max_s > 0:
                    scores.append((g.score / max_s) * 100)
            cat_avg = sum(scores) / len(scores) if scores else 0
            by_category[cat.name] = round(cat_avg, 1)
            weighted_sum += cat_avg * cat.weight
            total_weight += cat.weight

        uncat_avg = 0
        if other_grades:
            other_scores = []
            for g, a in other_grades:
                max_s = g.max_score if g.max_score else a.max_score
                if max_s > 0:
                    other_scores.append((g.score / max_s) * 100)
            uncat_avg = sum(other_scores) / len(other_scores) if other_scores else 0

        if total_weight > 0 and other_grades:
            final = (weighted_sum + uncat_avg) / (total_weight + 1.0)
        elif total_weight > 0:
            final = weighted_sum / total_weight
        elif other_grades:
            return self._simple_average(grades_data)
        else:
            final = weighted_sum

        return {
            "average": round(final, 1),
            "letter": self._to_letter(final),
            "by_category": by_category,
        }

    def _to_letter(self, pct: float) -> str:
        if pct >= 93: return "A"
        if pct >= 90: return "A-"
        if pct >= 87: return "B+"
        if pct >= 83: return "B"
        if pct >= 80: return "B-"
        if pct >= 77: return "C+"
        if pct >= 73: return "C"
        if pct >= 70: return "C-"
        if pct >= 67: return "D+"
        if pct >= 60: return "D"
        return "F"

    def assignment_stats(self, assignment_id: int) -> dict:
        grades = self.db.query(Grade).filter(Grade.assignment_id == assignment_id).all()
        if not grades:
            return {"count": 0, "average": 0, "median": 0, "min": 0, "max": 0, "distribution": []}
        assignment = self.db.query(Assignment).filter(Assignment.id == assignment_id).first()
        max_score = assignment.max_score if assignment else 100
        scores = sorted([g.score for g in grades if not g.is_excused])
        if not scores:
            return {"count": 0, "average": 0, "median": 0, "min": 0, "max": 0, "distribution": []}
        n = len(scores)
        avg = sum(scores) / n
        median = scores[n // 2]
        buckets = [0] * 10
        for s in scores:
            pct = int(s / max_score * 10)
            buckets[min(pct, 9)] += 1
        distribution = [
            {"range": f"{i*10}-{(i+1)*10}%", "count": c, "students": c}
            for i, c in enumerate(buckets)
        ]
        return {
            "count": n, "average": round(avg, 1), "median": round(median, 1),
            "min": min(scores), "max": max(scores), "distribution": distribution,
        }

    def class_overview(self, class_id: int) -> dict:
        students = self.db.query(Student).filter(Student.class_id == class_id).all()
        averages = []
        for s in students:
            result = self.student_average(s.id, class_id)
            averages.append({
                "student_id": s.id, "name": s.display_name,
                "average": result["average"], "letter": result["letter"],
                "has_grades": result["has_grades"],
            })
        averages.sort(key=lambda x: x["average"], reverse=True)
        graded_averages = [a for a in averages if a["has_grades"]]
        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for a in graded_averages:
            letter = a["letter"].replace("+", "").replace("-", "")
            if letter in grade_dist:
                grade_dist[letter] += 1
        class_avg = sum(a["average"] for a in graded_averages) / len(graded_averages) if graded_averages else 0
        return {
            "student_count": len(students), "class_average": round(class_avg, 1),
            "grade_distribution": grade_dist,
            "top_performer": graded_averages[0] if graded_averages else None,
            "needs_support": [a for a in graded_averages if a["average"] < 70],
        }


def init_db():
    Base.metadata.create_all(bind=engine)
    # SQLite does not add model columns to tables that already exist. Keep the
    # lightweight local database forward-compatible when new timestamps arrive.
    if "sqlite" in DATABASE_URL:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        additions = {
            "iep_goals": {"updated_at": "DATETIME"},
            "goal_benchmarks": {"created_at": "DATETIME"},
        }
        with engine.begin() as connection:
            for table, columns in additions.items():
                if table not in inspector.get_table_names():
                    continue
                existing = {column["name"] for column in inspector.get_columns(table)}
                for name, column_type in columns.items():
                    if name not in existing:
                        connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
