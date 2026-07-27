"""Student Rewards — classroom incentive points and transaction history."""
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Teacher, Class, Student, RewardTransaction, get_db
from app.middleware.auth import get_current_teacher

router = APIRouter(prefix="/api", tags=["rewards"])


class RewardEntry(BaseModel):
    student_id: int
    points: int = Field(..., ge=-10000, le=10000)
    note: str = ""


@router.get("/classes/{class_id}/rewards")
def rewards_overview(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    balances = dict(db.query(RewardTransaction.student_id, func.coalesce(func.sum(RewardTransaction.points), 0)).filter(
        RewardTransaction.class_id == class_id
    ).group_by(RewardTransaction.student_id).all())
    students = db.query(Student).filter(Student.class_id == class_id).order_by(Student.last_name, Student.first_name).all()
    transactions = db.query(RewardTransaction, Student).join(Student, Student.id == RewardTransaction.student_id).filter(
        RewardTransaction.class_id == class_id
    ).order_by(RewardTransaction.created_at.desc(), RewardTransaction.id.desc()).limit(40).all()
    return {
        "class": {"id": cls.id, "name": cls.name},
        "students": [{"student_id": s.id, "name": s.display_name, "balance": int(balances.get(s.id, 0))} for s in students],
        "transactions": [{
            "id": item.id, "student_id": student.id, "student_name": student.display_name,
            "points": item.points, "note": item.note, "created_at": item.created_at.isoformat(),
        } for item, student in transactions],
    }


@router.post("/classes/{class_id}/rewards")
def add_reward(class_id: int, req: RewardEntry, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    student = db.query(Student).filter(Student.id == req.student_id, Student.class_id == class_id).first()
    if not student:
        raise HTTPException(status_code=400, detail="Student must belong to this class")
    if req.points == 0:
        raise HTTPException(status_code=400, detail="Points must be greater or less than zero")
    transaction = RewardTransaction(class_id=class_id, student_id=student.id, points=req.points, note=req.note.strip())
    db.add(transaction)
    db.commit()
    balance = db.query(func.coalesce(func.sum(RewardTransaction.points), 0)).filter(
        RewardTransaction.class_id == class_id, RewardTransaction.student_id == student.id
    ).scalar()
    return {"status": "saved", "balance": int(balance)}
