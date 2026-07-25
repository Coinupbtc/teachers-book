"""IEP Goal Tracker routes — goals and measurable benchmark progress."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.models import Teacher, Class, Student, IEPGoal, GoalBenchmark, get_db
from app.middleware.auth import get_current_teacher

router = APIRouter(prefix="/api", tags=["goals"])


class GoalPayload(BaseModel):
    student_id: int
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    target_date: Optional[str] = None
    status: str = "in_progress"


class BenchmarkPayload(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    notes: str = ""
    progress: float = Field(default=0.0, ge=0, le=100)
    is_complete: bool = False


def goal_for_teacher(goal_id: int, teacher_id: int, db: Session) -> IEPGoal:
    goal = db.query(IEPGoal).options(joinedload(IEPGoal.benchmarks)).filter(IEPGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    cls = db.query(Class).filter(Class.id == goal.class_id, Class.teacher_id == teacher_id).first()
    if not cls:
        raise HTTPException(status_code=403, detail="Not your goal")
    return goal


def parsed_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Target date must use YYYY-MM-DD")


def goal_data(goal: IEPGoal) -> dict:
    benchmarks = [{
        "id": benchmark.id, "title": benchmark.title, "notes": benchmark.notes,
        "progress": benchmark.progress, "is_complete": benchmark.is_complete,
        "created_at": benchmark.created_at.isoformat() if benchmark.created_at else None,
        "updated_at": benchmark.updated_at.isoformat() if benchmark.updated_at else None,
    } for benchmark in goal.benchmarks]
    progress = sum(item["progress"] for item in benchmarks) / len(benchmarks) if benchmarks else 0
    return {
        "id": goal.id, "student_id": goal.student_id, "title": goal.title,
        "description": goal.description, "target_date": str(goal.target_date) if goal.target_date else None,
        "status": goal.status, "progress": round(progress, 1), "benchmarks": benchmarks,
        "created_at": goal.created_at.isoformat() if goal.created_at else None,
        "updated_at": (goal.updated_at or goal.created_at).isoformat() if (goal.updated_at or goal.created_at) else None,
    }


@router.get("/classes/{class_id}/goals")
def list_goals(class_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    students = db.query(Student).filter(Student.class_id == class_id).order_by(Student.last_name, Student.first_name).all()
    goals = db.query(IEPGoal).options(joinedload(IEPGoal.benchmarks)).filter(IEPGoal.class_id == class_id).order_by(IEPGoal.target_date, IEPGoal.created_at.desc()).all()
    return {
        "class": {"id": cls.id, "name": cls.name},
        "students": [{"student_id": student.id, "name": student.display_name} for student in students],
        "goals": [goal_data(goal) for goal in goals],
    }


@router.post("/classes/{class_id}/goals")
def create_goal(class_id: int, req: GoalPayload, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    if not db.query(Student).filter(Student.id == req.student_id, Student.class_id == class_id).first():
        raise HTTPException(status_code=400, detail="Student must belong to this class")
    goal = IEPGoal(class_id=class_id, student_id=req.student_id, title=req.title.strip(), description=req.description.strip(), target_date=parsed_date(req.target_date), status=req.status)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return {"id": goal.id, "status": "created"}


@router.put("/goals/{goal_id}")
def update_goal(goal_id: int, req: GoalPayload, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    goal = goal_for_teacher(goal_id, teacher.id, db)
    if not db.query(Student).filter(Student.id == req.student_id, Student.class_id == goal.class_id).first():
        raise HTTPException(status_code=400, detail="Student must belong to this class")
    goal.student_id, goal.title, goal.description = req.student_id, req.title.strip(), req.description.strip()
    goal.target_date, goal.status = parsed_date(req.target_date), req.status
    db.commit()
    return {"status": "updated"}


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    goal = goal_for_teacher(goal_id, teacher.id, db)
    db.delete(goal)
    db.commit()
    return {"status": "deleted"}


@router.post("/goals/{goal_id}/benchmarks")
def create_benchmark(goal_id: int, req: BenchmarkPayload, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    goal = goal_for_teacher(goal_id, teacher.id, db)
    benchmark = GoalBenchmark(goal_id=goal.id, title=req.title.strip(), notes=req.notes.strip(), progress=100 if req.is_complete else req.progress, is_complete=req.is_complete, sort_order=len(goal.benchmarks))
    db.add(benchmark)
    db.commit()
    return {"id": benchmark.id, "status": "created"}


@router.put("/benchmarks/{benchmark_id}")
def update_benchmark(benchmark_id: int, req: BenchmarkPayload, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    benchmark = db.query(GoalBenchmark).filter(GoalBenchmark.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    goal_for_teacher(benchmark.goal_id, teacher.id, db)
    benchmark.title, benchmark.notes = req.title.strip(), req.notes.strip()
    benchmark.is_complete = req.is_complete
    benchmark.progress = 100 if req.is_complete else req.progress
    db.commit()
    return {"status": "updated"}


@router.delete("/benchmarks/{benchmark_id}")
def delete_benchmark(benchmark_id: int, teacher: Teacher = Depends(get_current_teacher), db: Session = Depends(get_db)):
    benchmark = db.query(GoalBenchmark).filter(GoalBenchmark.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    goal_for_teacher(benchmark.goal_id, teacher.id, db)
    db.delete(benchmark)
    db.commit()
    return {"status": "deleted"}
