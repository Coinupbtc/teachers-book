"""
GradeBook Pro — Database Models

Core entities:
- Teacher (auth)
- Class (semester, subject, grade level)
- Student (belongs to a class)
- Assignment (has category, max score, due date)
- Grade (score per student per assignment)
- Category (weighted: tests=40%, homework=20%, etc.)
- Rubric (criteria for standards-based grading)
- RubricScore (score per criterion per student)
"""

import os
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text, Boolean,
    DateTime, Date, ForeignKey, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import (
    declarative_base, relationship, sessionmaker, Session
)
from passlib.context import CryptContext

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gradebook.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
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


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    name = Column(String(255), nullable=False)  # e.g., "Algebra I - Period 3"
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
    """Weighted category: Tests = 40%, Homework = 20%, etc."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    name = Column(String(100), nullable=False)
    weight = Column(Float, default=1.0)  # e.g., 0.4 for 40%
    drop_lowest = Column(Integer, default=0)  # drop N lowest scores
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
    assignment_type = Column(String(50), default="points")  # 'points' or 'rubric'
    rubric_id = Column(Integer, ForeignKey("rubrics.id"), nullable=True)
    extra_credit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    class_ = relationship("Class", back_populates="assignments")
    category = relationship("Category", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan")
    rubric = relationship("Rubric", backref="assignments")


class Grade(Base):
    """A single score for one student on one assignment."""
    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("student_id", "assignment_id", name="uq_student_assignment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    max_score = Column(Float, nullable=True)  # override per-student max (extra credit)
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
    criteria = Column(JSON, nullable=False)  # [{"name": "Clarity", "max": 4}, {"name": "Evidence", "max": 4}]
    created_at = Column(DateTime, default=datetime.utcnow)


class RubricScore(Base):
    """Score per criterion per student per rubric-based assignment."""
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


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String(20), default="present")  # present, absent, tardy, excused
    notes = Column(Text, default="")

    __table_args__ = (
        UniqueConstraint("student_id", "class_id", "date", name="uq_attendance"),
    )


# ─── Compute Engine ──────────────────────────────────────────────────────────

class GradeComputer:
    """Handles all grade calculations."""

    def __init__(self, db: Session):
        self.db = db

    def student_average(self, student_id: int, class_id: int) -> dict:
        """Calculate weighted/scaled average for a student across all assignments."""
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
            return self._simple_average(grades_data)

        return self._weighted_average(grades_data, categories)

    def _simple_average(self, grades_data: list) -> dict:
        """Simple average (no categories)."""
        scores = []
        for g, a, _ in grades_data:
            if g.is_excused:
                continue
            max_s = g.max_score if g.max_score else a.max_score
            pct = (g.score / max_s * 100) if max_s > 0 else 0
            scores.append(pct)

        avg = sum(scores) / len(scores) if scores else 0.0
        return {
            "average": round(avg, 1),
            "letter": self._to_letter(avg),
            "total_points": sum(g.score for g, a, _ in grades_data if not g.is_excused),
            "total_possible": sum(g.max_score or a.max_score for g, a, _ in grades_data if not g.is_excused),
            "assignments_graded": len(scores),
        }

    def _weighted_average(self, grades_data: list, categories: list) -> dict:
        """Weighted average by category."""
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

        for cat in categories:
            items = cat_grades[cat.id]
            if not items:
                continue
            # Drop lowest if configured
            sorted_items = sorted(items, key=lambda x: x[0].score / (x[0].max_score or x[1].max_score or 1))
            if cat.drop_lowest > 0:
                sorted_items = sorted_items[cat.drop_lowest:]

            scores = []
            for g, a in sorted_items:
                max_s = g.max_score if g.max_score else a.max_score
                pct = (g.score / max_s * 100) if max_s > 0 else 0
                scores.append(pct)

            cat_avg = sum(scores) / len(scores) if scores else 0
            weighted_sum += cat_avg * cat.weight
            total_weight += cat.weight

        # Uncategorized assignments (straight average)
        if other_grades:
            other_scores = []
            for g, a in other_grades:
                max_s = g.max_score if g.max_score else a.max_score
                pct = (g.score / max_s * 100) if max_s > 0 else 0
                other_scores.append(pct)
            uncat_avg = sum(other_scores) / len(other_scores) if other_scores else 0
            # Treat as one weighted category if no categories have weights
            if total_weight == 0:
                return self._simple_average(grades_data)
        else:
            uncat_avg = 0

        if total_weight > 0:
            final = (weighted_sum + uncat_avg) / (total_weight + (1.0 if other_grades else 0.0))
        else:
            final = weighted_sum

        return {
            "average": round(final, 1),
            "letter": self._to_letter(final),
            "by_category": {
                c.name: self._category_avg(cat_grades[c.id]) for c in categories
            },
        }

    def _category_avg(self, items: list) -> float:
        if not items:
            return 0.0
        scores = []
        for g, a in items:
            max_s = g.max_score if g.max_score else a.max_score
            pct = (g.score / max_s * 100) if max_s > 0 else 0
            scores.append(pct)
        return round(sum(scores) / len(scores), 1)

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
        """Distribution stats for a single assignment."""
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

        # Histogram buckets (as percentages)
        buckets = [0] * 10  # 0-10%, 10-20%, etc.
        for s in scores:
            pct = int(s / max_score * 10)
            if pct >= 10:
                pct = 9
            buckets[pct] += 1

        distribution = []
        for i, count in enumerate(buckets):
            distribution.append({
                "range": f"{i*10}-{(i+1)*10}%",
                "count": count,
                "students": count,
            })

        return {
            "count": n,
            "average": round(avg, 1),
            "median": round(median, 1),
            "min": min(scores),
            "max": max(scores),
            "distribution": distribution,
        }

    def class_overview(self, class_id: int) -> dict:
        """Overview stats for a whole class."""
        students = self.db.query(Student).filter(Student.class_id == class_id).all()
        averages = []
        for s in students:
            result = self.student_average(s.id, class_id)
            averages.append({
                "student_id": s.id,
                "name": s.display_name,
                "average": result["average"],
                "letter": result["letter"],
            })

        # Sort by average descending
        averages.sort(key=lambda x: x["average"], reverse=True)

        # Bin students into grade groups
        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for a in averages:
            letter = a["letter"].replace("+", "").replace("-", "")
            if letter in grade_dist:
                grade_dist[letter] += 1

        class_avg = sum(a["average"] for a in averages) / len(averages) if averages else 0

        return {
            "student_count": len(students),
            "class_average": round(class_avg, 1),
            "grade_distribution": grade_dist,
            "top_performer": averages[0] if averages else None,
            "needs_support": [a for a in averages if a["average"] < 70],
        }


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
