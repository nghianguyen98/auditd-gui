"""
api/main.py — FastAPI application entry point
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router, ensure_admin_user
from routers.sessions import router as sessions_router
from routers.dashboard import router as dashboard_router
from routers.alerts import router as alerts_router
from routers.settings import router as settings_router
from routers.ingest import router as ingest_router
from routers.nodes import router as nodes_router
from db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Auditd GUI API starting...")
    ensure_admin_user()
    yield
    logger.info("Auditd GUI API stopped.")


app = FastAPI(
    title="Auditd GUI API",
    description="Linux User Activity Tracker",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # nginx handles external access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(dashboard_router)
app.include_router(alerts_router)
app.include_router(settings_router)
app.include_router(ingest_router)
app.include_router(nodes_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
