"""Teachers B00k — Application Factory"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import init_db
from app.routes.auth import router as auth_router
from app.routes.classes import router as class_routes
from app.routes.grades import router as grade_routes
from app.routes.gradebook import router as gb_routes
from app.routes.rewards import router as reward_routes
from app.routes.goals import router as goal_routes


def create_app() -> FastAPI:
    app = FastAPI(
        title="Teachers B00k",
        version="2.0.0",
        description="The gradebook that doesn't suck. Weighted grading, rubrics, analytics, CSV export.",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Startup — create tables
    @app.on_event("startup")
    def startup():
        init_db()

    # Health check
    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "2.0.0"}

    # Mount routers
    app.include_router(auth_router)
    app.include_router(class_routes)
    app.include_router(grade_routes)
    app.include_router(gb_routes)
    app.include_router(reward_routes)
    app.include_router(goal_routes)

    # Serve static frontend (SPA)
    frontend_dir = settings.FRONTEND_DIR
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()
