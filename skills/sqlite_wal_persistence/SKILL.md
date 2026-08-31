---
name: sqlite_wal_persistence
description: Methodologie d'ingenierie pour l'implementation de bases de donnees SQLite ACID hautement concurrentes avec mode WAL, verrous non-bloquants et ecritures atomiques. A activer lors de la creation de tables, transactions et persistance de donnees.
version: 1.0.0
tags: [database, sqlite, wal, acid, storage, bdd, persistence, transactions, sql, migration]
---

# Playbook SQLite WAL & Persistance Atomique

## 1. Mission & Perimetre d'Application
Ce playbook definit le standard strict d'architecture et de persistance des donnees relationnelles sous SQLite en environnement multi-agents concurrent. Il elimine les erreurs de verrouillage (`database is locked`), garantit l'integrite ACID et interdit toute injection SQL.

## 2. Directives Fondamentales & Anti-Patterns Interdits
- **Configuration WAL & Pragmas Obligatoires** : Configurer systematiquement lors de chaque connexion :
  * `PRAGMA journal_mode = WAL;` (permet des lectures concurrentes non bloquantes pendant les ecritures).
  * `PRAGMA busy_timeout = 5000;` (attente deterministe de 5 secondes avant toute levee d'erreur de verrou).
  * `PRAGMA synchronous = NORMAL;` (performance optimale avec garantie de non-corruption).
  * `PRAGMA foreign_keys = ON;` (respect des contraintes d'integrite referentielle).
- **Requetes Parametrees a 100%** : Utiliser EXCLUSIVEMENT les parametres positionnels `?` pour toutes les variables d'entree. Interdiction absolue des interpolations de chaines (`f"SELECT ... WHERE id = '{id}'"`).
- **Gestionnaire Transactionnel `with conn:`** : Encapsuler chaque ecriture dans un bloc transactionnel assurant un `COMMIT` automatique en cas de succes et un `ROLLBACK` immediat en cas d'exception.

## 3. Implementation de Reference de Production

```python
from __future__ import annotations

import logging
from pathlib import Path
import sqlite3
from typing import Any, Iterator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SqliteDatabaseManager:
    """Gestionnaire de persistance SQLite avec mode WAL et isolation ACID."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_pragmas()

    def _init_pragmas(self) -> None:
        """Initialise le mode WAL et les pragmas critiques au demarrage."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        """Fournit une connexion configuree avec row_factory sous forme de dictionnaire."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def execute_transaction(self, query: str, params: tuple[Any, ...] | list[Any] = ()) -> int:
        """Execute une requete d'ecriture atomique avec commit et rollback garanti."""
        with self.get_connection() as conn:
            try:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount
            except sqlite3.Error as err:
                conn.rollback()
                logger.error("Echec transactionnel SQLite: %s (Requete: %s)", err, query)
                raise RuntimeError(f"Erreur SQL securisee : {err}") from err

    def fetch_all(self, query: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        """Execute une requete de lecture non-bloquante et renvoie une liste de dictionnaires."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def fetch_one(self, query: str, params: tuple[Any, ...] | list[Any] = ()) -> dict[str, Any] | None:
        """Execute une requete de lecture unitaire et renvoie le dictionnaire ou None."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
```

## 4. Checklist de Validation Deterministe
- [ ] Le mode WAL (`PRAGMA journal_mode = WAL`) est actif.
- [ ] Le timeout (`PRAGMA busy_timeout = 5000`) est defini sur chaque connexion.
- [ ] Zero concatenation de chaines : 100% des parametres utilisent les marqueurs `?`.
- [ ] Les operations de mutation de donnees sont encapsulees dans des blocs de transaction explicites.
- [ ] Les cles etrangeres sont activees (`PRAGMA foreign_keys = ON`).
