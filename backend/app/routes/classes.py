"""GradeBook Pro — Class & Student Routes"""
from fastapi import APIRouter, Depends, HTTPException, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import json

from app.models import Teacher, Class, Student, Category, Assignment, Grade, get_db
from app.middleware.auth import get_current_teacher

router = APIRouter(prefix="/api", tags=["classes"])


class ClassCreate(BaseModel):
    name: str
    subject: str = ""
    grade_level: str = ""
    semester: str = "Fall 2026"
    school_year: str = "2026-2027"


@router.get("/classes")
def list_classes(teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    classes = (
        db.query(Class)
        .filter(Class.teacher_id == teacher.id)
        .options(joinedload(Class.students), joinedload(Class.assignments))
        .order_by(Class.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "subject": c.subject,
            "semester": c.semester,
            "student_count": len(c.students),
            "assignment_count": len(c.assignments),
        }
        for c in classes
    ]


@router.post("/classes")
def create_class(req: ClassCreate, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = Class(
        teacher_id=teacher.id,
        name=req.name,
        subject=req.subject,
        grade_level=req.grade_level,
        semester=req.semester,
        school_year=req.school_year,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    # Create default categories
    defaults = [
        ("Tests", 0.35, 0), ("Quizzes", 0.20, 1),
        ("Homework", 0.20, 2), ("Classwork", 0.15, 3), ("Participation", 0.10, 4),
    ]
    for name, weight, order in defaults:
        db.add(Category(class_id=cls.id, name=name, weight=weight, sort_order=order))
    db.commit()
    return {"id": cls.id, "name": cls.name}


def _get_class_or_404(class_id: int, teacher_id: int, db: Session) -> Class:
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


@router.get("/classes/{class_id}")
def get_class(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = _get_class_or_404(class_id, teacher.id, db)
    student_count = db.query(Student).filter(Student.class_id == class_id).count()
    assignment_count = db.query(Assignment).filter(Assignment.class_id == class_id).count()
    return {
        "id": cls.id, "name": cls.name, "subject": cls.subject,
        "semester": cls.semester, "grade_level": cls.grade_level,
        "student_count": student_count, "assignment_count": assignment_count,
    }


# ─── Student Routes ──────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    email: str = ""
    student_id: str = ""


class StudentUpdate(BaseModel):
    first_name: str
    last_name: str
    email: str = ""
    student_id: str = ""


@router.get("/classes/{class_id}/students")
def list_students(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    _get_class_or_404(class_id, teacher.id, db)
    students = db.query(Student).filter(Student.class_id == class_id).order_by(Student.last_name, Student.first_name).all()
    return [
        {"id": s.id, "first_name": s.first_name, "last_name": s.last_name,
         "display_name": s.display_name, "email": s.email,
         "student_id": s.student_id, "notes": s.notes}
        for s in students
    ]


@router.post("/classes/{class_id}/students")
def add_student(class_id: int, req: StudentCreate, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    _get_class_or_404(class_id, teacher.id, db)
    student = Student(class_id=class_id, **req.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return {"id": student.id, "display_name": student.display_name}


@router.post("/classes/{class_id}/students/batch")
def batch_add_students(
    class_id: int,
    students_json: str = Form(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    _get_class_or_404(class_id, teacher.id, db)
    try:
        data = json.loads(students_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Expected JSON array")

    added = []
    for row in data:
        fn = row.get("first_name", "").strip()
        ln = row.get("last_name", "").strip()
        if not fn or not ln:
            continue
        s = Student(class_id=class_id, first_name=fn, last_name=ln,
                    email=row.get("email", ""), student_id=row.get("student_id", ""))
        db.add(s)
        added.append(s.display_name)
    db.commit()

    return {"status": "ok", "added": len(added)}


@router.put("/students/{student_id}")
def update_student(student_id: int, req: StudentUpdate, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    _get_class_or_404(student.class_id, teacher.id, db)
    if not req.first_name.strip() or not req.last_name.strip():
        raise HTTPException(status_code=400, detail="First and last name are required")
    student.first_name = req.first_name.strip()
    student.last_name = req.last_name.strip()
    student.email = req.email.strip()
    student.student_id = req.student_id.strip()
    db.commit()
    return {"status": "updated", "display_name": student.display_name}


@router.delete("/students/{student_id}")
def remove_student(student_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    cls = db.query(Class).filter(Class.id == student.class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=403, detail="Not your class")
    db.delete(student)
    db.commit()
    return {"status": "deleted"}


# ─── Category Routes ──────────────────────────────────────────────────────────


# list_categories: handled in grades.py (richer response with weight_pct + assignment_count)
