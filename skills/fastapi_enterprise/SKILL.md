---
name: fastapi_enterprise
description: Playbook d'ingenierie pour la conception d'APIs REST modulaires et robustes avec FastAPI, Pydantic v2 et gestion transactionnelle des erreurs. A activer lors de la creation de routeurs HTTP, validation de payloads et endpoints REST.
version: 1.0.0
tags: [backend, fastapi, pydantic, rest, api, routes, validation, http, async, crud]
---

# Playbook FastAPI Enterprise Edition

## 1. Mission & Perimetre d'Application
Ce playbook definit le standard strict de developpement des services d'API REST de grade production. Il garantit l'isolation modulaire, la validation rigoureuse des donnees a l'entree et a la sortie, et la gestion sans faille des codes de statut HTTP.

## 2. Directives Fondamentales & Anti-Patterns Interdits
- **Typage Strict Pydantic v2** : Utiliser systematiquement `ConfigDict(extra='forbid', validate_assignment=True)` sur 100% des schemas de requete pour interdire toute propriete non declaree.
- **Schemas de Reponse Explicites** : Declarer imperativement `response_model=...` et `status_code=...` sur chaque routeur.
- **Decoupage Modulaire** : Isoler chaque domaine dans son propre `APIRouter` sous `api/routes/` et monter les routeurs dans l'application principale via `app.include_router(router, prefix='/api/v1/...')`.
- **Gestion des Exceptions** : Lever des exceptions HTTP explicites (`fastapi.HTTPException`) avec messages clairs. Interdiction formelle des clauses `except: pass` silencieuses.
- **Asynchronisme Eprouve** : Utiliser `async/await` pour les operations d'I/O reseau et les appels clients HTTP (`httpx.AsyncClient`).

## 3. Implementation de Reference de Production

```python
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/items", tags=["Items Management"])


# --- Schemas de Donnees Pydantic v2 Stricts ---

class ItemBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    
    name: str = Field(..., min_length=2, max_length=100, description="Nom unique de l'article")
    price: float = Field(..., gt=0.0, description="Prix unitaire positif en USD")
    category: str = Field("General", min_length=2, max_length=50, description="Categorie de l'article")


class CreateItemRequest(ItemBase):
    pass


class ItemResponse(ItemBase):
    id: str = Field(..., description="Identifiant unique genere")
    is_active: bool = Field(True, description="Statut de disponibilite")
    created_at: str = Field(..., description="Horodatage ISO-8601 UTC")


# --- Endpoints REST Standardises ---

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ItemResponse,
    summary="Creer un nouvel article de maniere atomique",
)
async def create_item(payload: CreateItemRequest) -> ItemResponse:
    try:
        # Simulation d'insertion dans le domaine/stockage
        item_id = "item_12345678"
        created_at_iso = "2026-08-30T22:00:00Z"
        
        response_data = ItemResponse(
            id=item_id,
            name=payload.name,
            price=payload.price,
            category=payload.category,
            is_active=True,
            created_at=created_at_iso,
        )
        return response_data
    except Exception as err:
        logger.error("Erreur lors de la creation de l'article: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Echec de creation de l'article: {str(err)}",
        )


@router.get(
    "/{item_id}",
    status_code=status.HTTP_200_OK,
    response_model=ItemResponse,
    summary="Recuperer un article par son identifiant unique",
)
async def get_item(item_id: str) -> ItemResponse:
    if not item_id or item_id == "unknown":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article avec l'identifiant '{item_id}' introuvable.",
        )
    return ItemResponse(
        id=item_id,
        name="Article Reference",
        price=49.99,
        category="General",
        is_active=True,
        created_at="2026-08-30T22:00:00Z",
    )
```

## 4. Checklist de Validation Deterministe
- [ ] 100% des modeles Pydantic definissent `ConfigDict(extra="forbid")`.
- [ ] Les verbes HTTP respectent les standards REST (POST = 201, GET/PUT/PATCH = 200, DELETE = 200/204).
- [ ] Tous les endpoints declarent explicitement `response_model` et un code `status_code`.
- [ ] Aucune variable brute non validee n'est directement executee sans validation de type.
- [ ] Le code passe 100% de conformite AST via l'outil `ast_validator`.
