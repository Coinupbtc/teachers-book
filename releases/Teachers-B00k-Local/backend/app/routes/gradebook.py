"""GradeBook Pro — Gradebook View, Analytics, Reports, CSV Export"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import func
from typing import Optional

from app.models import (
    Teacher, Class, Student, Category, Assignment, Grade, GradeComputer, get_db
)
from app.middleware.auth import get_current_teacher

router = APIRouter(prefix="/api", tags=["gradebook"])


@router.get("/classes/{class_id}/gradebook")
def gradebook_view(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    """Full gradebook view with eager-loaded data — 4 queries total regardless of class size."""
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    # Eager-load ALL data in 3 queries (students, assignments, grades)
    students = (
        db.query(Student)
        .filter(Student.class_id == class_id)
        .order_by(Student.last_name, Student.first_name)
        .all()
    )
    assignments = (
        db.query(Assignment)
        .filter(Assignment.class_id == class_id)
        .order_by(Assignment.due_date, Assignment.name)
        .all()
    )
    # Bulk load all grades for this class
    grades = (
        db.query(Grade)
        .join(Student, Grade.student_id == Student.id)
        .filter(Student.class_id == class_id)
        .all()
    )
    categories = (
        db.query(Category)
        .filter(Category.class_id == class_id)
        .order_by(Category.sort_order)
        .all()
    )

    # Build index: (student_id, assignment_id) → Grade
    grade_map: dict = {}
    for g in grades:
        grade_map[(g.student_id, g.assignment_id)] = g

    computer = GradeComputer(db)
    student_ids = [s.id for s in students]
    assignment_ids = [a.id for a in assignments]

    # Build rows
    rows = []
    for s in students:
        student_grades = {}
        for a in assignments:
            g = grade_map.get((s.id, a.id))
            if g:
                max_s = g.max_score or a.max_score
                student_grades[a.id] = {
                    "grade_id": g.id,
                    "score": g.score,
                    "max_score": max_s,
                    "is_excused": g.is_excused,
                    "late": g.late,
                    "comments": g.comments,
                    "graded_at": g.graded_at.isoformat() if g.graded_at else None,
                    "percentage": round(g.score / max_s * 100, 1) if max_s > 0 else 0,
                }

        avg_data = computer.student_average(s.id, class_id)
        rows.append({
            "student_id": s.id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "name": s.display_name,
            "grades": student_grades,
            "average": avg_data["average"],
            "letter": avg_data["letter"],
            "has_grades": avg_data["has_grades"],
        })

    class_stats = computer.class_overview(class_id)

    return {
        "class": {"id": cls.id, "name": cls.name, "subject": cls.subject},
        "categories": [{"id": c.id, "name": c.name, "weight": c.weight} for c in categories],
        "assignments": [
            {
                "id": a.id, "name": a.name, "max_score": a.max_score,
                "category_id": a.category_id,
                "due_date": str(a.due_date) if a.due_date else None,
                "extra_credit": a.extra_credit,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in assignments
        ],
        "students": rows,
        "stats": class_stats,
    }


@router.get("/classes/{class_id}/analytics")
def class_analytics(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    computer = GradeComputer(db)
    stats = computer.class_overview(class_id)
    assignments = db.query(Assignment).filter(Assignment.class_id == class_id).all()
    assignment_stats = [
        {"id": a.id, "name": a.name, "stats": computer.assignment_stats(a.id)}
        for a in assignments
    ]
    return {"overview": stats, "assignments": assignment_stats}


@router.get("/classes/{class_id}/reports")
def class_reports(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    computer = GradeComputer(db)
    students = (
        db.query(Student)
        .filter(Student.class_id == class_id)
        .order_by(Student.last_name, Student.first_name)
        .all()
    )
    reports = []
    for s in students:
        avg_data = computer.student_average(s.id, class_id)
        recent_grades = (
            db.query(Grade, Assignment)
            .join(Assignment, Grade.assignment_id == Assignment.id)
            .filter(Grade.student_id == s.id)
            .order_by(Assignment.due_date.desc().nullslast())
            .limit(10)
            .all()
        )
        reports.append({
            "student_id": s.id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "name": s.display_name,
            "average": avg_data["average"],
            "letter": avg_data["letter"],
            "has_grades": avg_data["has_grades"],
            "by_category": avg_data.get("by_category", {}),
            "recent_assignments": [
                {
                    "name": a.name,
                    "score": g.score,
                    "max": g.max_score or a.max_score,
                    "percentage": round(g.score / (g.max_score or a.max_score) * 100, 1),
                }
                for g, a in recent_grades
            ],
        })
    return {"class_name": cls.name, "student_count": len(reports), "reports": reports}


@router.get("/classes/{class_id}/export/csv")
def export_csv(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    """Export gradebook as CSV."""
    data = gradebook_view(class_id, teacher, db)

    lines = []
    header = ["Student Name", "Average", "Letter Grade"]
    for a in data["assignments"]:
        header.append(f"{a['name']} ({a['max_score']}pts)")
    lines.append(",".join(f'"{h}"' for h in header))

    for s in data["students"]:
        row = [s["name"], str(s["average"]), s["letter"]]
        for a in data["assignments"]:
            grade = s["grades"].get(a["id"])
            if grade:
                row.append(str(grade["score"]))
            else:
                row.append("")
        lines.append(",".join(row))

    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{data["class"]["name"]}_gradebook.csv"'},
    )
