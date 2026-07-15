"""GradeBook Pro — Category, Assignment & Grade Entry Routes"""
from fastapi import APIRouter, Depends, HTTPException, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import Optional
import json

from app.models import (
    Teacher, Class, Category, Assignment, Grade, Student, GradeComputer, get_db
)
from app.middleware.auth import get_current_teacher

router = APIRouter(prefix="/api", tags=["categories"])


# ─── Category Routes ─────────────────────────────────────────────────────────

class CategoryUpdate(BaseModel):
    name: str
    weight: float = 1.0
    drop_lowest: int = 0


@router.get("/classes/{class_id}/categories")
def list_categories(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    cats = db.query(Category).filter(Category.class_id == class_id).order_by(Category.sort_order).all()
    total_weight = sum(c.weight for c in cats) or 1
    return [
        {
            "id": c.id, "name": c.name, "weight": c.weight,
            "weight_pct": round(c.weight / total_weight * 100, 1),
            "drop_lowest": c.drop_lowest, "sort_order": c.sort_order,
            "assignment_count": db.query(Assignment).filter(Assignment.category_id == c.id).count(),
        }
        for c in cats
    ]


@router.put("/categories/{category_id}")
def update_category(category_id: int, req: CategoryUpdate, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    # Verify ownership via class
    cls = db.query(Class).filter(Class.id == cat.class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=403, detail="Not your class")
    cat.name = req.name
    cat.weight = req.weight
    cat.drop_lowest = req.drop_lowest
    db.commit()
    return {"status": "updated"}


# ─── Assignment Routes ───────────────────────────────────────────────────────

class AssignmentCreate(BaseModel):
    name: str
    max_score: float = 100.0
    category_id: Optional[int] = None
    due_date: Optional[str] = None
    description: str = ""
    extra_credit: bool = False


class AssignmentUpdate(BaseModel):
    name: str
    max_score: float = 100.0
    category_id: Optional[int] = None
    due_date: Optional[str] = None
    description: str = ""
    extra_credit: bool = False


class GradeCreate(BaseModel):
    """A score entered directly from the gradebook grid."""
    student_id: int
    assignment_id: int
    score: float
    max_score: Optional[float] = None
    is_excused: bool = False
    late: bool = False
    comments: str = ""


@router.get("/classes/{class_id}/assignments")
def list_assignments(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    assignments = (
        db.query(Assignment)
        .filter(Assignment.class_id == class_id)
        .order_by(Assignment.due_date.desc().nullslast(), Assignment.created_at.desc())
        .all()
    )
    return [
        {
            "id": a.id, "name": a.name, "max_score": a.max_score,
            "category_id": a.category_id,
            "due_date": str(a.due_date) if a.due_date else None,
            "extra_credit": a.extra_credit, "assignment_type": a.assignment_type,
            "graded_count": db.query(Grade).filter(Grade.assignment_id == a.id, Grade.score > 0).count(),
        }
        for a in assignments
    ]


@router.post("/classes/{class_id}/assignments")
def create_assignment(class_id: int, req: AssignmentCreate, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    due = None
    if req.due_date:
        try:
            due = date.fromisoformat(req.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format (use YYYY-MM-DD)")

    assignment = Assignment(
        class_id=class_id, name=req.name, max_score=req.max_score,
        category_id=req.category_id, due_date=due,
        description=req.description, extra_credit=req.extra_credit,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {"id": assignment.id, "name": assignment.name}


@router.put("/assignments/{assignment_id}")
def update_assignment(assignment_id: int, req: AssignmentUpdate, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    cls = db.query(Class).filter(Class.id == assignment.class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=403, detail="Not your assignment")
    if req.max_score <= 0:
        raise HTTPException(status_code=400, detail="Points possible must be greater than zero")
    if req.category_id is not None and not db.query(Category).filter(Category.id == req.category_id, Category.class_id == cls.id).first():
        raise HTTPException(status_code=400, detail="Category must belong to this class")
    try:
        due = date.fromisoformat(req.due_date) if req.due_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (use YYYY-MM-DD)")
    assignment.name = req.name.strip()
    assignment.max_score = req.max_score
    assignment.category_id = req.category_id
    assignment.due_date = due
    assignment.description = req.description
    assignment.extra_credit = req.extra_credit
    db.commit()
    return {"status": "updated"}


@router.delete("/assignments/{assignment_id}")
def delete_assignment(assignment_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    cls = db.query(Class).filter(Class.id == assignment.class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=403, detail="Not your assignment")
    db.delete(assignment)
    db.commit()
    return {"status": "deleted"}


# ─── Grade Routes ────────────────────────────────────────────────────────────

class GradeUpdate(BaseModel):
    score: float
    max_score: Optional[float] = None
    is_excused: bool = False
    late: bool = False
    comments: str = ""


@router.post("/classes/{class_id}/grades")
def create_grade(
    class_id: int,
    req: GradeCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Create or update a grade, with ownership checks for both records."""
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    student = db.query(Student).filter(Student.id == req.student_id, Student.class_id == class_id).first()
    assignment = db.query(Assignment).filter(
        Assignment.id == req.assignment_id, Assignment.class_id == class_id
    ).first()
    if not student or not assignment:
        raise HTTPException(status_code=400, detail="Student and assignment must belong to this class")
    if req.score < 0:
        raise HTTPException(status_code=400, detail="Score cannot be negative")

    grade = db.query(Grade).filter(
        Grade.student_id == student.id, Grade.assignment_id == assignment.id
    ).first()
    if grade:
        grade.score = req.score
        grade.max_score = req.max_score
        grade.is_excused = req.is_excused
        grade.late = req.late
        grade.comments = req.comments
        grade.graded_at = datetime.utcnow()
    else:
        grade = Grade(
            student_id=student.id, assignment_id=assignment.id, score=req.score,
            max_score=req.max_score, is_excused=req.is_excused, late=req.late,
            comments=req.comments,
        )
        db.add(grade)
    db.commit()
    db.refresh(grade)
    return {"grade_id": grade.id, "status": "saved"}


@router.get("/assignments/{assignment_id}/grades")
def get_grades(assignment_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Verify ownership
    cls = db.query(Class).filter(Class.id == assignment.class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=403, detail="Not your class")

    grades = (
        db.query(Grade, Student)
        .join(Student, Grade.student_id == Student.id)
        .filter(Grade.assignment_id == assignment_id)
        .order_by(Student.last_name, Student.first_name)
        .all()
    )
    computer = GradeComputer(db)
    stats = computer.assignment_stats(assignment_id)

    return {
        "assignment": {"id": assignment.id, "name": assignment.name, "max_score": assignment.max_score, "category_id": assignment.category_id},
        "stats": stats,
        "grades": [
            {
                "grade_id": g.id, "student_id": s.id, "student_name": s.display_name,
                "score": g.score, "max_score": g.max_score, "is_excused": g.is_excused,
                "late": g.late, "comments": g.comments,
                "percentage": round(g.score / (g.max_score or assignment.max_score) * 100, 1)
                              if (g.max_score or assignment.max_score) > 0 else 0,
            }
            for g, s in grades
        ],
    }


@router.put("/grades/{grade_id}")
def update_grade(grade_id: int, req: GradeUpdate, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    grade = db.query(Grade).filter(Grade.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    # Verify ownership through student → class → teacher
    student = db.query(Student).filter(Student.id == grade.student_id).first()
    if student:
        cls = db.query(Class).filter(Class.id == student.class_id, Class.teacher_id == teacher.id).first()
        if not cls:
            raise HTTPException(status_code=403, detail="Not your student")
    grade.score = req.score
    if req.max_score is not None:
        grade.max_score = req.max_score
    grade.is_excused = req.is_excused
    grade.late = req.late
    grade.comments = req.comments
    grade.graded_at = datetime.utcnow()
    db.commit()
    return {"status": "updated"}


@router.delete("/grades/{grade_id}")
def delete_grade(grade_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    """Clear an entered score so it returns to the ungraded state."""
    grade = db.query(Grade).filter(Grade.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    student = db.query(Student).filter(Student.id == grade.student_id).first()
    cls = db.query(Class).filter(Class.id == student.class_id, Class.teacher_id == teacher.id).first() if student else None
    if not cls:
        raise HTTPException(status_code=403, detail="Not your grade")
    db.delete(grade)
    db.commit()
    return {"status": "cleared"}


@router.post("/assignments/{assignment_id}/grades/batch")
def batch_update_grades(
    assignment_id: int,
    grades_json: str = Form(...),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Batch update grades. Validates ownership before making any changes."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    cls = db.query(Class).filter(Class.id == assignment.class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=403, detail="Not your class")

    try:
        data = json.loads(grades_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Expected array")

    updated = 0
    errors = []
    for entry in data:
        grade = db.query(Grade).filter(Grade.id == entry.get("grade_id")).first()
        if not grade:
            errors.append({"grade_id": entry.get("grade_id"), "error": "not found"})
            continue
        grade.score = entry.get("score", grade.score)
        grade.late = entry.get("late", grade.late)
        grade.is_excused = entry.get("is_excused", grade.is_excused)
        if "max_score" in entry:
            grade.max_score = entry["max_score"]
        grade.graded_at = datetime.utcnow()
        updated += 1
    db.commit()
    return {"status": "ok", "updated": updated, "errors": errors if errors else None}
