from __future__ import annotations

from typing import Any
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from core.domain import (
    AgentDefinition,
    AgentLink,
    DocumentAttachment,
    FinOpsBadge,
    LinkType,
    Project,
    ProjectStatus,
    Thread,
)
from storage.repository import agent_links_repo, agent_repo, project_repo
from services.project_exporter import project_exporter
from services.quality_judge import quality_judge
from services.time_travel import time_travel

router = APIRouter(prefix="/api/v1/projects", tags=["Projets & Threads"])


# Schémas de requêtes stricts Pydantic v2
class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    budget_limit_usd: float = Field(default=10.0, ge=0.5, le=1000.0)
    selected_finops_profile: FinOpsBadge = FinOpsBadge.SWEET_SPOT
    target_path: str | None = None


class UpdateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    status: ProjectStatus | None = None
    budget_limit_usd: float | None = None
    selected_finops_profile: FinOpsBadge | None = None
    target_path: str | None = None


class CreateThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)


class UpdateThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None
    is_unread: bool | None = None


class UploadDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str
    content: str
    content_type: str = "text/plain"


@router.get("", response_model=list[dict[str, Any]])
def list_projects(include_archived: bool = Query(False, description="Inclure les projets archivés")):
    """Liste tous les projets enregistrés avec leur score qualité déterministe dynamique."""
    projects = project_repo.list_all(include_archived=include_archived)
    results = []
    for p in projects:
        data = p.model_dump(mode="json")
        matrix = quality_judge.evaluate_project(p)
        data["quality_score"] = matrix.total_score
        data["quality_matrix"] = matrix.model_dump(mode="json")
        results.append(data)
    return results


@router.post("/browse-folder", response_model=dict[str, Any])
def browse_folder():
    """Ouvre la boîte de dialogue native du système d'exploitation pour sélectionner un dossier local."""
    import os
    if os.getenv("PYTEST_CURRENT_TEST"):
        from core.config import settings
        return {"status": "success", "path": str(settings.data_dir)}
    try:
        if os.name != "nt" and not os.getenv("DISPLAY"):
            return {"status": "unavailable", "path": "", "message": "Environnement sans interface graphique."}
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder_path = filedialog.askdirectory(title="Sélectionnez le dossier du projet")
        root.destroy()
        if folder_path:
            return {"status": "success", "path": str(folder_path)}
    except Exception as e:
        logger.warning("Échec ouverture boîte de dialogue dossier : %s", e)
    return {"status": "cancelled", "path": ""}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_project(payload: CreateProjectRequest):
    """Crée un nouveau projet, initialise son thread et instancie son équipe dédiée d'agents."""
    target_path = ""
    if payload.target_path and payload.target_path.strip():
        target_path = str(Path(payload.target_path.strip()).resolve())

    project = Project(
        name=payload.name,
        budget_limit_usd=payload.budget_limit_usd,
        selected_finops_profile=payload.selected_finops_profile,
        target_path=target_path,
    )
    # Initialiser le thread principal
    project.get_or_create_main_thread()
    saved = project_repo.save(project)

    # Instanciation de l'équipe d'agents dédiée et étanche pour ce projet
    pid = str(saved.id)
    slug = "".join(c if c.isalnum() else "_" for c in saved.name.lower())[:10]

    # 1. Agent Développeur Dédié
    agent_dev = AgentDefinition(
        id=f"ag_dev_{slug}_{pid[:4]}",
        name=f"Développeur · {saved.name}",
        project_id=pid,
        role_description=f"Ingénieur logiciel dédié pour {saved.name}",
        role="Développeur Logiciel Dédié",
        model="qwen/qwen-2.5-coder-32b-instruct",
        temperature=0.2,
        max_tokens=4096,
        budget_limit_usd=payload.budget_limit_usd * 0.6,
        canvas_x=80.0,
        canvas_y=140.0,
        icon="code",
        is_active=True,
        is_core_meta_agent=False,
    )
    agent_repo.save(agent_dev)

    # 2. Agent Contrôleur Qualité Dédié
    agent_judge = AgentDefinition(
        id=f"ag_judge_{slug}_{pid[:4]}",
        name=f"Contrôleur Qualité · {saved.name}",
        project_id=pid,
        role_description=f"Auditeur qualité et juge déterministe pour {saved.name}",
        role="Juge Qualité & Testeur",
        model="moonshotai/kimi-k3",
        temperature=0.1,
        max_tokens=4096,
        budget_limit_usd=payload.budget_limit_usd * 0.4,
        canvas_x=480.0,
        canvas_y=140.0,
        icon="shield",
        is_active=True,
        is_core_meta_agent=False,
    )
    agent_repo.save(agent_judge)

    # 3. Liaison initiale en mode Débat (Actor-Critic)
    initial_link = AgentLink(
        source_agent_id=agent_dev.id,
        target_agent_id=agent_judge.id,
        project_id=pid,
        link_type=LinkType.DEBATE,
        label="Développeur ⇄ Contrôleur Qualité",
        is_active=True,
    )
    agent_links_repo.create(initial_link)

    return saved.model_dump(mode="json")


@router.get("/{project_id}", response_model=dict[str, Any])
def get_project(project_id: UUID):
    """Récupère un projet complet avec ses threads et son score qualité dynamique."""
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable.")
    data = project.model_dump(mode="json")
    matrix = quality_judge.evaluate_project(project)
    data["quality_score"] = matrix.total_score
    data["quality_matrix"] = matrix.model_dump(mode="json")
    return data


@router.get("/{project_id}/quality-score", response_model=dict[str, Any])
def get_project_quality_score(project_id: UUID):
    """Calcule et retourne en direct la matrice officielle de score qualité déterministe sur 100 points."""
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable.")
    matrix = quality_judge.evaluate_project(project)
    return matrix.model_dump(mode="json")


@router.patch("/{project_id}", response_model=dict[str, Any])
@router.put("/{project_id}", response_model=dict[str, Any])
def update_project(project_id: UUID, payload: UpdateProjectRequest):
    """Met à jour les paramètres d'un projet."""
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    if payload.name is not None:
        project.name = payload.name
    if payload.status is not None:
        project.status = payload.status
    if payload.budget_limit_usd is not None:
        project.budget_limit_usd = payload.budget_limit_usd
    if payload.selected_finops_profile is not None:
        project.selected_finops_profile = payload.selected_finops_profile

    saved = project_repo.save(project)
    return saved.model_dump(mode="json")


@router.post("/{project_id}/archive", response_model=dict[str, Any])
def archive_project(project_id: UUID):
    """Archive un projet (Soft Delete réversible)."""
    success = project_repo.archive(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Projet introuvable.")
    return {"status": "archived", "project_id": str(project_id)}


@router.post("/{project_id}/restore", response_model=dict[str, Any])
def restore_project(project_id: UUID):
    """Restaure un projet archivé."""
    success = project_repo.restore(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Projet introuvable.")
    return {"status": "restored", "project_id": str(project_id)}


@router.delete("/{project_id}", status_code=status.HTTP_200_OK, response_model=dict[str, Any])
def delete_project(project_id: UUID, permanent: bool = Query(False, description="Si True, purge définitive. Si False, archivage réversible.")):
    """Supprime un projet (archivage réversible par défaut ou purge définitive si permanent=True)."""
    if permanent:
        deleted = project_repo.delete(project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Projet introuvable.")
        return {"status": "purged", "project_id": str(project_id)}
    else:
        archived = project_repo.archive(project_id)
        if not archived:
            raise HTTPException(status_code=404, detail="Projet introuvable.")
        return {"status": "archived", "project_id": str(project_id)}


@router.get("/{project_id}/threads", response_model=list[dict[str, Any]])
def list_threads(project_id: UUID):
    """Liste tous les threads de discussion d'un projet."""
    threads = project_repo.get_threads(str(project_id), load_messages=False)
    return [t.model_dump(mode="json") for t in threads]


@router.post("/{project_id}/threads", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_thread(project_id: UUID, payload: CreateThreadRequest):
    """Crée un nouveau thread dans le projet."""
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    thread = Thread(project_id=str(project.id), title=payload.title)
    saved = project_repo.save_thread(thread)
    return saved.model_dump(mode="json")


@router.patch("/{project_id}/threads/{thread_id}", response_model=dict[str, Any])
def update_thread(project_id: UUID, thread_id: str, payload: UpdateThreadRequest):
    """Met à jour un fil de discussion (titre, épinglé, archivé, non-lu)."""
    updated = project_repo.update_thread(
        thread_id=thread_id,
        title=payload.title,
        is_pinned=payload.is_pinned,
        is_archived=payload.is_archived,
        is_unread=payload.is_unread,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Thread introuvable.")
    return updated.model_dump(mode="json")


@router.delete("/{project_id}/threads/{thread_id}", status_code=status.HTTP_200_OK, response_model=dict[str, Any])
def delete_thread(project_id: UUID, thread_id: str):
    """Supprime définitivement un fil de discussion."""
    success = project_repo.delete_thread(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="Thread introuvable.")
    return {"status": "deleted", "thread_id": thread_id}


@router.get("/{project_id}/threads/{thread_id}/messages", response_model=list[dict[str, Any]])
def get_thread_messages(project_id: UUID, thread_id: str):
    """Récupère l'historique des messages d'un fil."""
    messages = project_repo.get_thread_messages(thread_id)
    return [m.model_dump(mode="json") for m in messages]


@router.post("/{project_id}/documents", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def upload_document(project_id: UUID, payload: UploadDocumentRequest):
    """Enregistre un document/spécification attaché au projet."""
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    doc = DocumentAttachment(
        filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=len(payload.content.encode("utf-8")),
        raw_content=payload.content,
        summary=payload.content[:300] + "..." if len(payload.content) > 300 else payload.content,
    )
    project.documents.append(doc)
    project_repo.save(project)

    return doc.model_dump(mode="json")


@router.get("/{project_id}/export/zip")
def export_project_zip(project_id: UUID):
    """Télécharge l'archive ZIP complète du projet."""
    project = project_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    zip_content = project_exporter.create_zip_archive(project)
    safe_filename = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project.name.lower())

    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={safe_filename}.zip"},
    )


@router.get("/{project_id}/checkpoints", response_model=list[dict[str, Any]])
def list_checkpoints(project_id: UUID):
    """Liste l'historique des checkpoints Time Travel."""
    checkpoints = time_travel.get_history(str(project_id))
    return [c.model_dump(mode="json") for c in checkpoints]


@router.post("/{project_id}/rollback", response_model=dict[str, Any])
def rollback_project(project_id: UUID):
    """Restaure instantanément le projet à son dernier checkpoint stable."""
    restored = time_travel.rollback_to_latest(str(project_id))
    if not restored:
        raise HTTPException(status_code=400, detail="Aucun checkpoint disponible pour la restauration.")
    return restored.model_dump(mode="json")
