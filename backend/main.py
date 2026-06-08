"""
Samarth — FastAPI Application Entry Point
"""
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from config import settings
from database import connect_db, close_db
from api import auth, patients, therapists, exercises, sessions, pose, analysis, sensors, reports, analytics, notifications
from ws_handlers import session_ws_router, camera_ws_router


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🌱 Starting {settings.APP_NAME} backend...")
    settings.ensure_dirs()
    await connect_db()

    # Inject PS1 pipeline path into sys.path so adapter can import it
    ps1_path = str(settings.get_ps1_path())
    if ps1_path not in sys.path:
        sys.path.insert(0, ps1_path)
        logger.info(f"✅ PS1 pipeline mounted at: {ps1_path}")

    yield

    logger.info("Shutting down...")
    await close_db()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Samarth API",
    description=(
        "AI-Guided Physiotherapy Rehabilitation Platform API. "
        "Wraps PS1 (Computer Vision) with PS2/PS3 integration stubs."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (exercise GIFs, demo assets) ────────────────────────────────
os.makedirs("static/exercises", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── REST API Routers ──────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(auth.router,          prefix=f"{PREFIX}/auth",          tags=["Authentication"])
app.include_router(patients.router,      prefix=f"{PREFIX}/patients",      tags=["Patients"])
app.include_router(therapists.router,    prefix=f"{PREFIX}/therapists",    tags=["Therapists"])
app.include_router(exercises.router,     prefix=f"{PREFIX}/exercises",     tags=["Exercises"])
app.include_router(sessions.router,      prefix=f"{PREFIX}/sessions",      tags=["Sessions"])
app.include_router(pose.router,          prefix=f"{PREFIX}/pose",          tags=["PS1 Pose Engine"])
app.include_router(analysis.router,      prefix=f"{PREFIX}/analysis",      tags=["PS2 Exercise Analysis"])
app.include_router(sensors.router,       prefix=f"{PREFIX}/sensor",        tags=["PS3 Sensor Hub"])
app.include_router(reports.router,       prefix=f"{PREFIX}/reports",       tags=["Reports"])
app.include_router(analytics.router,     prefix=f"{PREFIX}/analytics",     tags=["Analytics"])
app.include_router(notifications.router, prefix=f"{PREFIX}/notifications", tags=["Notifications"])

# ── WebSocket Routers ─────────────────────────────────────────────────────────
app.include_router(session_ws_router,  tags=["WebSocket — Live Session"])
app.include_router(camera_ws_router,   tags=["WebSocket — Camera Validation"])


# ── Global Exception Handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "ps2_mode": "real" if settings.PS2_USE_REAL_MODEL else "mock",
        "ps3_mode": "real" if settings.PS3_USE_REAL_SENSOR else "simulated",
        "storage": settings.STORAGE_BACKEND,
    }
