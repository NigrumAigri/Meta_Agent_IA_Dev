#!/usr/bin/env bash
# ==============================================================================
# Script de Démarrage 1-Clic pour macOS & Linux
# Meta Developer Agent v5.0.0 — Enterprise Edition
# ==============================================================================

set -e

echo "==============================================================================="
echo "  🚀 META DEVELOPER AGENT v5.0.0 — ENTERPRISE COMMAND CENTER"
echo "  Démarrage en 1-Clic via Docker Compose"
echo "==============================================================================="
echo ""

# 1. Vérification de Docker
if ! command -v docker &> /dev/null; then
    echo "❌ [ERREUR] Docker n'est pas installé sur cette machine."
    echo "Veuillez installer Docker depuis https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# 2. Vérification du démon Docker
if ! docker info &> /dev/null; then
    echo "❌ [ERREUR] Impossible de joindre le démon Docker. Assurez-vous que Docker est bien lancé."
    exit 1
fi

# 3. Initialisation du fichier .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "ℹ️ [INFO] Initialisation automatique du fichier .env..."
        cp .env.example .env
        echo "✅ [SUCCÈS] Fichier .env initialisé."
    fi
fi

# 4. Lecture du port configuré (8000 par défaut)
APP_PORT=$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d '=' -f2 || echo "8000")
APP_PORT=${APP_PORT:-8000}

echo "📦 [1/3] Construction et démarrage du conteneur sécurisé..."
docker compose up -d --build

echo "⏳ [2/3] Attente de la disponibilité du serveur (Port $APP_PORT)..."
sleep 3

URL="http://localhost:$APP_PORT"
echo "🌐 [3/3] Ouverture automatique dans votre navigateur ($URL)..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    open "$URL" || true
elif command -v xdg-open &> /dev/null; then
    xdg-open "$URL" || true
fi

echo ""
echo "==============================================================================="
echo "  ✅ APPLICATION OPÉRATIONNELLE SUR : $URL"
echo "  - Pour arrêter : docker compose stop"
echo "  - Pour voir les logs en direct : docker compose logs -f"
echo "==============================================================================="
echo ""
