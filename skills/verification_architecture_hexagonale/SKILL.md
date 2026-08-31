---
name: verification_architecture_hexagonale
description: Standard architectural d'isolation du Domaine metier, inversion des dependances (DIP) et decouplage par Ports et Adaptateurs (Clean Architecture / Hexagonale). A activer lors de la modelisation du domaine, separation des couches et conception de services.
version: 1.0.0
tags: [architecture, hexagonal, clean_architecture, ddd, ports, adapters, domain, interfaces, decouplage, refactoring]
---

# Playbook Architecture Hexagonale & Inversion des Dependances

## 1. Mission & Perimetre d'Application
Ce playbook definit le standard de modelisation logicielle pour garantir que le **Cœur de Metier (Domaine)** demeure 100% pur, agnostique et independant de toute technologie d'infrastructure (bases de donnees, frameworks Web, protocoles reseau ou interfaces externes).

## 2. Directives Fondamentales & Anti-Patterns Interdits
- **Regle d'Or des Dependances** : Les dependances pointent TOUJOURS vers le centre (Domaine). Le Domaine ne doit JAMAIS importer `FastAPI`, `SQLite`, `httpx` ou des modules de persistance.
- **Ports (Interfaces Abstraites)** : Definir les contrats d'entree et de sortie sous forme de `typing.Protocol` ou `abc.ABC` a l'interieur du domaine.
- **Adaptateurs (Infrastructure & I/O)** : Implementer les details techniques a l'exterieur (ex: `storage/sqlite_repository.py`, `api/routes/item_router.py`).
- **Entites & Value Objects Purs** : Les objets du domaine utilisent des modeles Pydantic v2 `ConfigDict(extra="forbid", frozen=True)` pour garantir l'immutabilite.

## 3. Implementation de Reference de Production

```python
from __future__ import annotations

from typing import Protocol
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. COUCHE DOMAINE (Zero dependance externe / Pure metier)
# ==============================================================================

class ProjectEntity(BaseModel):
    """Entite centrale du Domaine metier avec validation stricte."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    
    id: str = Field(..., description="Identifiant unique immutable")
    name: str = Field(..., min_length=2, max_length=100)
    budget_usd: float = Field(..., gt=0.0)
    is_archived: bool = Field(default=False)

    def can_spend(self, amount: float) -> bool:
        """Regle metier pure evaluable sans appel I/O."""
        return not self.is_archived and self.budget_usd >= amount


class ProjectRepositoryPort(Protocol):
    """Port secondaire (SPI) : Contrat d'interface que l'infrastructure doit satisfaire."""
    
    def get_by_id(self, project_id: str) -> ProjectEntity | None:
        ...
        
    def save(self, project: ProjectEntity) -> ProjectEntity:
        ...


# ==============================================================================
# 2. COUCHE SERVICE / CAS D'USAGE (Orchestration du Domaine)
# ==============================================================================

class AllocateBudgetUseCase:
    """Cas d'usage metier dependant uniquement des Ports abstraits."""

    def __init__(self, repository: ProjectRepositoryPort) -> None:
        self.repository = repository

    def execute(self, project_id: str, amount_to_spend: float) -> ProjectEntity:
        project = self.repository.get_by_id(project_id)
        if not project:
            raise ValueError(f"Projet {project_id} introuvable dans le domaine.")
        
        if not project.can_spend(amount_to_spend):
            raise PermissionError(f"Budget insuffisant ou projet archive pour {project_id}.")
        
        updated_project = ProjectEntity(
            id=project.id,
            name=project.name,
            budget_usd=project.budget_usd - amount_to_spend,
            is_archived=project.is_archived,
        )
        return self.repository.save(updated_project)


# ==============================================================================
# 3. COUCHE INFRASTRUCTURE / ADAPTATEUR (Details techniques SQLite)
# ==============================================================================

class SqliteProjectAdapter(ProjectRepositoryPort):
    """Adaptateur concret satisfaisant le Port du Domaine sans polluer le Domaine."""

    def __init__(self, db_connection: Any) -> None:
        self.db = db_connection

    def get_by_id(self, project_id: str) -> ProjectEntity | None:
        # Requete parametree et conversion en Entite Domaine
        row = self.db.fetch_one("SELECT id, name, budget_usd, is_archived FROM projects WHERE id = ?", (project_id,))
        if not row:
            return None
        return ProjectEntity(
            id=row["id"],
            name=row["name"],
            budget_usd=float(row["budget_usd"]),
            is_archived=bool(row["is_archived"]),
        )

    def save(self, project: ProjectEntity) -> ProjectEntity:
        self.db.execute(
            "INSERT INTO projects (id, name, budget_usd, is_archived) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET budget_usd = excluded.budget_usd, is_archived = excluded.is_archived;",
            (project.id, project.name, project.budget_usd, 1 if project.is_archived else 0),
        )
        return project
```

## 4. Checklist de Validation Deterministe
- [ ] Le module Domaine n'a aucun import provenant de frameworks d'infrastructure (`fastapi`, `sqlite3`, etc.).
- [ ] Chaque interaction de stockage passe par un `Protocol` ou une classe abstraite `ABC`.
- [ ] Les entites du domaine protegent leurs invariants et regles metier.
- [ ] L'injection de dependance permet d'interchanger les adaptateurs sans modifier le Domaine.
