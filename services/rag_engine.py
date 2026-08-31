from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)


class RagDocumentChunk:
    """Morceau de document indexé pour le RAG."""

    def __init__(self, doc_name: str, section: str, content: str, path: str):
        self.doc_name = doc_name
        self.section = section
        self.content = content
        self.path = path
        self.tokens = self._tokenize(content)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())


class RagEngine:
    """Moteur RAG Hybride (BM25 + Analyse Lexicale) indexant la Knowledge Base."""

    # --- Fichiers a exclure de l'index BM25 ---
    # Le MOC est deja injecte separement dans <knowledge_index>.
    # Ajouter ici tout fichier a ignorer (ex: brouillons, doublons).
    EXCLUDED_FILES: list[str] = [
        "00_MOC_MAITRISE_AGENTS_IA.md",
        "08_Fine_Tuning_Et_Customization_Modeles_Agents_IA.md",
    ]

    # Nombre de lignes de chevauchement entre chunks adjacents.
    # Permet de ne pas perdre le contexte aux frontieres de sections.
    OVERLAP_LINES: int = 6

    def __init__(self, kb_dir: Path | None = None) -> None:
        self.kb_dir = kb_dir or (settings.v5_root / "knowledge_base")
        self.chunks: list[RagDocumentChunk] = []
        self.doc_freqs: dict[str, int] = {}
        self.avg_chunk_len: float = 0.0
        self.is_indexed: bool = False

    def index_knowledge_base(self) -> int:
        """Parse et indexe tous les fichiers markdown de la base de connaissances."""
        self.chunks = []
        self.doc_freqs = {}

        if not self.kb_dir.exists():
            logger.warning("Répertoire Knowledge Base introuvable: %s", self.kb_dir)
            return 0

        for file_path in self.kb_dir.glob("*.md"):
            if file_path.name in self.EXCLUDED_FILES:
                logger.info("Fichier exclu de l'index RAG: %s", file_path.name)
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                # Decoupage par sections Markdown (## ou ###)
                sections = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)
                prev_tail_lines: list[str] = []
                for sec in sections:
                    sec_clean = sec.strip()
                    if len(sec_clean) < 40:
                        continue
                    # Chevauchement : prefixer le chunk courant avec
                    # les dernieres lignes du chunk precedent
                    if prev_tail_lines:
                        overlap_text = "\n".join(prev_tail_lines)
                        combined = overlap_text + "\n" + sec_clean
                    else:
                        combined = sec_clean
                    first_line = sec_clean.split("\n")[0]
                    chunk = RagDocumentChunk(
                        doc_name=file_path.name,
                        section=first_line,
                        content=combined,
                        path=str(file_path),
                    )
                    self.chunks.append(chunk)
                    # Memoriser les dernieres lignes pour l'overlap suivant
                    sec_lines = sec_clean.split("\n")
                    prev_tail_lines = sec_lines[-self.OVERLAP_LINES:]
            except Exception as e:
                logger.error("Erreur indexation %s: %s", file_path, e)

        if not self.chunks:
            return 0

        # Calcul des fréquences de documents (IDF)
        total_len = 0
        for chunk in self.chunks:
            total_len += len(chunk.tokens)
            unique_tokens = set(chunk.tokens)
            for t in unique_tokens:
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

        self.avg_chunk_len = total_len / len(self.chunks)
        self.is_indexed = True
        logger.info("Knowledge Base RAG indexée avec succès: %d chunks", len(self.chunks))
        return len(self.chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Recherche les extraits les plus pertinents via BM25."""
        if not self.is_indexed:
            self.index_knowledge_base()

        query_tokens = re.findall(r"\w+", query.lower())
        if not query_tokens or not self.chunks:
            return []

        scores: list[tuple[float, RagDocumentChunk]] = []
        k1 = 1.5
        b = 0.75
        n_chunks = len(self.chunks)

        for chunk in self.chunks:
            score = 0.0
            chunk_len = len(chunk.tokens)
            token_counts: dict[str, int] = {}
            for t in chunk.tokens:
                token_counts[t] = token_counts.get(t, 0) + 1

            for qt in query_tokens:
                if qt in token_counts:
                    tf = token_counts[qt]
                    df = self.doc_freqs.get(qt, 1)
                    idf = math.log((n_chunks - df + 0.5) / (df + 0.5) + 1.0)
                    numerator = tf * (k1 + 1)
                    denominator = tf + k1 * (1 - b + b * (chunk_len / (self.avg_chunk_len or 1.0)))
                    score += idf * (numerator / denominator)

            if score > 0:
                scores.append((score, chunk))

        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for s, chunk in scores[:top_k]:
            results.append({
                "document": chunk.doc_name,
                "section": chunk.section,
                "score": round(s, 3),
                "content": chunk.content,
                "file_path": chunk.path,
            })
        return results


# Instance singleton
rag_engine = RagEngine()
