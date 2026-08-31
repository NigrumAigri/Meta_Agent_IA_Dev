from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.rag_engine import rag_engine
from services.lessons_engine import lessons_engine
from storage.repository import lessons_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["RAG & Mémoire Épisodique"])
alias_router = APIRouter(prefix="/rag", tags=["RAG & Mémoire Épisodique"])


class RagSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=10)


class CreateLessonRequest(BaseModel):
    topic: str
    problem_statement: str
    solution_applied: str
    prevention_rule: str = ""
    project_id: str | None = None
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0)


@router.get("/summary", response_model=dict[str, Any])
@alias_router.get("/summary", response_model=dict[str, Any])
def get_rag_summary():
    """Renvoie le sommaire de la base de connaissances et de la mémoire épisodique."""
    if not rag_engine.is_indexed:
        rag_engine.index_knowledge_base()
    
    lessons = lessons_repo.list_lessons()
    doc_count = len(list(rag_engine.kb_dir.glob("*.md"))) if rag_engine.kb_dir.exists() else 0

    return {
        "status": "ready",
        "kb_documents_count": doc_count,
        "kb_chunks_count": len(rag_engine.chunks),
        "lessons_learned_count": len(lessons),
        "avg_chunk_length": round(rag_engine.avg_chunk_len, 1),
    }


@router.post("/search", response_model=list[dict[str, Any]])
@alias_router.post("/search", response_model=list[dict[str, Any]])
def search_knowledge_base(payload: RagSearchRequest):
    """Recherche les extraits les plus pertinents de la Knowledge Base via BM25."""
    results = rag_engine.search(query=payload.query, top_k=payload.top_k)
    return results


@router.get("/documents", response_model=list[dict[str, Any]])
@alias_router.get("/documents", response_model=list[dict[str, Any]])
def list_knowledge_documents():
    """Liste tous les documents sources de la Knowledge Base."""
    if not rag_engine.is_indexed:
        rag_engine.index_knowledge_base()

    if not rag_engine.kb_dir.exists():
        return []

    docs = []
    for file_path in sorted(rag_engine.kb_dir.glob("*.md")):
        chunks = [c for c in rag_engine.chunks if c.doc_name == file_path.name]
        docs.append({
            "filename": file_path.name,
            "path": str(file_path),
            "size_bytes": file_path.stat().st_size,
            "chunks_count": len(chunks),
        })
    return docs


@router.get("/lessons", response_model=list[dict[str, Any]])
@alias_router.get("/lessons", response_model=list[dict[str, Any]])
def list_lessons(project_id: str | None = None):
    """Liste toutes les leçons apprises enregistrées."""
    lessons = lessons_repo.list_lessons(project_id=project_id)
    return [l.model_dump(mode="json") for l in lessons]


@router.post("/lessons", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
@alias_router.post("/lessons", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_lesson(payload: CreateLessonRequest):
    """Enregistre une nouvelle leçon d'apprentissage dans la mémoire épisodique SQLite WAL."""
    lesson = lessons_engine.record_lesson(
        topic=payload.topic,
        problem_statement=payload.problem_statement,
        solution_applied=payload.solution_applied,
        prevention_rule=payload.prevention_rule,
        project_id=payload.project_id,
        confidence_score=payload.confidence_score,
    )
    return lesson.model_dump(mode="json")


@router.post("/lessons/{lesson_id}/convert-to-rule", response_model=dict[str, Any])
@alias_router.post("/lessons/{lesson_id}/convert-to-rule", response_model=dict[str, Any])
def convert_lesson_to_rule(lesson_id: str):
    """Convertit automatiquement une règle de prévention de leçon en règle modulaire physique (.md)."""
    success = lessons_engine.convert_lesson_to_rule(lesson_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Impossible de convertir cette leçon : leçon introuvable ou règle de prévention vide."
        )
    return {
        "status": "success",
        "message": "Leçon convertie avec succès en Règle Modulaire active.",
    }


@router.delete("/lessons/{lesson_id}", response_model=dict[str, Any])
@alias_router.delete("/lessons/{lesson_id}", response_model=dict[str, Any])
def delete_lesson(lesson_id: str):
    """Supprime une leçon de la mémoire épisodique."""
    deleted = lessons_repo.delete_lesson(lesson_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Leçon introuvable.")
    return {
        "status": "success",
        "message": f"Leçon {lesson_id} supprimée avec succès.",
    }
