"""GradeBook Pro — Auth Routes (login, signup, me, logout with JWT)"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.models import Teacher, get_db
from app.config import settings
from app.middleware.auth import get_current_teacher

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    email: str
    name: str
    password: str
    invite_code: str = ""


@router.post("/signup")
def signup(req: SignupRequest, response: Response, db: Session = Depends(get_db)):
    if settings.INVITE_CODE and req.invite_code != settings.INVITE_CODE:
        raise HTTPException(status_code=403, detail="A valid invite code is required to create an account")
    existing = db.query(Teacher).filter(Teacher.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    teacher = Teacher(email=req.email, name=req.name)
    teacher.set_password(req.password)
    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    token = teacher.make_token()
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.JWT_EXPIRY_HOURS * 3600,
        secure=False,  # Set True in production with HTTPS
    )
    return {"status": "ok", "teacher_id": teacher.id, "name": teacher.name, "token": token}


@router.post("/login")
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    teacher = db.query(Teacher).filter(Teacher.email == req.email).first()
    if not teacher or not teacher.verify_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = teacher.make_token()
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.JWT_EXPIRY_HOURS * 3600,
        secure=False,
    )
    return {"status": "ok", "teacher_id": teacher.id, "name": teacher.name, "token": token}


@router.get("/me")
def get_me(teacher: Teacher = Depends(get_current_teacher)):
    return {"id": teacher.id, "email": teacher.email, "name": teacher.name, "school": teacher.school}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("token")
    return {"status": "ok"}
