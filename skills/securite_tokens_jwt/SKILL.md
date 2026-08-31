---
name: securite_tokens_jwt
description: Protocole de securite et de cryptographie pour l'authentification par Tokens JWT, hachage des mots de passe et gestion des sessions sans etat. A activer lors de la gestion de l'authentification, verification de signatures et securisation d'acces.
version: 1.0.0
tags: [security, jwt, auth, token, password, argon2, bcrypt, claims, authentification, session, cryptographie]
---

# Playbook Securite des Tokens JWT & Authentification

## 1. Mission & Perimetre d'Application
Ce playbook definit le standard cryptographique obligatoire pour l'authentification des utilisateurs et des agents. Il regit la generation securisee des tokens (Access & Refresh), le hachage irreversibilise des mots de passe et la validation rigoureuse des signatures sans etat (Stateless).

## 2. Directives Fondamentales & Anti-Patterns Interdits
- **Algorithmes Cryptographiques Stricts** : Utiliser exclusivement `HS256` (avec secret d'au moins 256 bits) ou `RS256`. Interdiction formelle d'accepter l'algorithme `none` (vulnerabilite critique).
- **Duree de Vie Limitee & Rotation** :
  * Access Token : Duree de vie courte (15 a 30 minutes maximum).
  * Refresh Token : Duree de vie controlee (7 a 14 jours maximum) stocke de maniere securisee.
- **Hachage des Mots de Passe** : Ne JAMAIS stocker de mot de passe en clair. Utiliser exclusivement `hashlib.pbkdf2_hmac`, `bcrypt` ou `argon2` avec un sel cryptographique aleatoire de 16 octets minimum.
- **Claims Standardises Obligatoires** : Inclure systematiquement `sub` (sujet/ID), `iat` (date d'emission), `exp` (date d'expiration) et `jti` (identifiant unique de token pour revocation).

## 3. Implementation de Reference de Production

```python
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class TokenClaims(BaseModel):
    """Payload de claims JWT valide et type."""
    model_config = ConfigDict(extra="forbid")
    
    sub: str = Field(..., description="Identifiant unique de l'utilisateur ou de l'agent")
    roles: list[str] = Field(default_factory=list, description="Roles et autorisations attribues")
    iat: int = Field(default_factory=lambda: int(time.time()), description="Date d'emission (timestamp UTC)")
    exp: int = Field(..., description="Date d'expiration obligatoire (timestamp UTC)")
    jti: str = Field(..., description="Identifiant unique du token pour prevenir le rejeu")


class JwtSecurityManager:
    """Gestionnaire deterministe de hachage et de signature de tokens JWT."""

    def __init__(self, secret_key: str, access_ttl_seconds: int = 900) -> None:
        if len(secret_key.encode("utf-8")) < 32:
            raise ValueError("La cle secrete JWT doit comporter au moins 32 octets (256 bits).")
        self._secret = secret_key.encode("utf-8")
        self._access_ttl = access_ttl_seconds

    @staticmethod
    def hash_password(password: str, salt: bytes | None = None) -> str:
        """Hache un mot de passe avec PBKDF2-HMAC-SHA256 et sel cryptographique."""
        salt = salt or os.urandom(16)
        iterations = 100_000
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"pbkdf2:sha256:{iterations}${salt.hex()}${key.hex()}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verifie un mot de passe en temps constant contre les attaques temporelles."""
        try:
            parts = hashed.split("$")
            if len(parts) != 3:
                return False
            _, salt_hex, key_hex = parts
            salt = bytes.fromhex(salt_hex)
            expected_key = bytes.fromhex(key_hex)
            iterations = 100_000
            actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(actual_key, expected_key)
        except Exception:
            return False

    def create_access_token(self, subject_id: str, roles: list[str] | None = None) -> str:
        """Genere un Access Token JWT signe en HS256."""
        now = int(time.time())
        claims = TokenClaims(
            sub=subject_id,
            roles=roles or [],
            iat=now,
            exp=now + self._access_ttl,
            jti=os.urandom(12).hex(),
        )
        
        header = {"alg": "HS256", "typ": "JWT"}
        b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        b64_payload = base64.urlsafe_b64encode(json.dumps(claims.model_dump()).encode()).decode().rstrip("=")
        
        signing_input = f"{b64_header}.{b64_payload}".encode()
        signature = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        b64_sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        
        return f"{b64_header}.{b64_payload}.{b64_sig}"

    def decode_and_verify_token(self, token: str) -> TokenClaims:
        """Valide la signature cryptographique et l'expiration du token JWT."""
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Format de token JWT invalide.")
        
        b64_header, b64_payload, b64_sig = parts
        signing_input = f"{b64_header}.{b64_payload}".encode()
        expected_sig = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        
        pad_len = 4 - (len(b64_sig) % 4)
        actual_sig = base64.urlsafe_b64decode((b64_sig + "=" * (pad_len % 4)).encode())
        
        if not hmac.compare_digest(actual_sig, expected_sig):
            raise PermissionError("Signature cryptographique JWT invalide.")
        
        payload_pad = 4 - (len(b64_payload) % 4)
        payload_json = json.loads(base64.urlsafe_b64decode((b64_payload + "=" * (payload_pad % 4)).encode()))
        
        claims = TokenClaims.model_validate(payload_json)
        if claims.exp < int(time.time()):
            raise TimeoutError("Le token JWT a expire.")
            
        return claims
```

## 4. Checklist de Validation Deterministe
- [ ] La cle secrete utilisee comporte 32 octets (256 bits) minimum.
- [ ] L'algorithme `none` est formellement rejete.
- [ ] La verification du mot de passe et de la signature utilise `hmac.compare_digest` (temps constant).
- [ ] Le claim d'expiration `exp` est present et valide a chaque decodage.
- [ ] Les mots de passe utilisent un sel unique et PBKDF2 / Argon2.
