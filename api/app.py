from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from storage.sqlite_db import db
from services.skills_registry import skills_registry
from services.rules_registry import rules_registry

# Import des routeurs modulaires v5
from api.routes.projects import router as projects_router
from api.routes.chat import router as chat_router
from api.routes.copilot import router as copilot_router
from api.routes.agents import router as agents_router
from api.routes.proposals import router as proposals_router
from api.routes.finops import router as finops_router
from api.routes.mcp import router as mcp_router
from api.routes.pillars import router as pillars_router, alias_router as pillars_alias_router
from api.routes.hitl import router as hitl_router
from api.routes.config import router as config_router
from api.routes.rag import router as rag_router, alias_router as rag_alias_router

logger = logging.getLogger(__name__)


from services.benchmarks_client import benchmarks_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisation au démarrage de l'application."""
    logger.info("Démarrage de Meta Developer Agent v5.0.0 Enterprise...")
    # 1. Schéma SQLite WAL
    db.init_schema()
    # 2. Seeding des registres
    skills_registry.sync_filesystem_to_db()
    rules_registry.sync_filesystem_to_db()
    # 3. Démarrage du planificateur de synchronisation des benchmarks (Toutes les heures + rattrapage au boot)
    benchmarks_client.start_background_scheduler()
    logger.info("Base SQLite WAL, 7 Piliers et Planificateur Benchmarks prêts (Fréquence horaire).")
    yield
    logger.info("Arrêt de Meta Developer Agent v5.0.0 Enterprise.")


app = FastAPI(
    title="Meta Developer Agent API",
    version="5.0.0",
    description="API REST Enterprise pour l'Architecture Multi-Agents, Command Center & FinOps",
    lifespan=lifespan,
)

# Configuration CORS pour intégration frontend fluide
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montage de tous les routeurs API v1
app.include_router(projects_router)
app.include_router(chat_router)
app.include_router(copilot_router)
app.include_router(agents_router)
app.include_router(proposals_router)
app.include_router(finops_router)
app.include_router(mcp_router)
app.include_router(pillars_router)
app.include_router(pillars_alias_router)
app.include_router(rag_router)
app.include_router(rag_alias_router)
app.include_router(hitl_router)
app.include_router(config_router)

# Montage des fichiers statiques frontend
static_dir = settings.v5_root / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health", tags=["Système"])
def health_check():
    """Vérification de l'état de santé du serveur."""
    return {
        "status": "healthy",
        "version": "5.0.0",
        "database": "sqlite_wal",
        "openrouter_connected": settings.is_openrouter_connected,
    }


@app.get("/", tags=["Frontend"])
def serve_index():
    """Sert l'application SPA sans mise en cache navigateur."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(
            str(index_file),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return {
        "app": "Meta Developer Agent v5.0.0 Enterprise",
        "status": "Backend API opérationnel",
        "docs_url": "/docs",
    }
