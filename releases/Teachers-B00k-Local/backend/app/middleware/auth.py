"""GradeBook Pro — Auth Middleware

JWT-based authentication via cookie or Authorization header.
No in-memory state — works across tabs, restarts, and multiple clients.
"""
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from starlette.status import HTTP_401_UNAUTHORIZED

from app.models import Teacher, get_db

# Support both cookie and header-based auth
security = HTTPBearer(auto_error=False)


async def get_current_teacher(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Teacher:
    """Extract teacher from JWT cookie (preferred) or Authorization header."""
    token = None

    # Try cookie first
    token = request.cookies.get("token")

    # Fall back to Authorization header
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    teacher_id = Teacher.verify_token(token)
    if teacher_id is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    return teacher
