@echo off
setlocal enabledelayedexpansion
title Meta Developer Agent v5.0.0 — Command Center

echo ===============================================================================
echo   🚀 META DEVELOPER AGENT v5.0.0 — ENTERPRISE COMMAND CENTER
echo   Demarrage en 1-Clic via Docker Compose
echo ===============================================================================
echo.

:: 1. Verification de la presence de Docker
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERREUR] Docker n'est pas installe sur votre ordinateur.
    echo Veuillez installer Docker Desktop depuis https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

:: 2. Verification que le demon Docker est bien en cours d'execution
docker info >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Docker Desktop est en cours de demarrage... Veuillez patienter.
    timeout /t 5 /nobreak >nul
    docker info >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERREUR] Impossible de joindre le demon Docker.
        echo Assurez-vous que Docker Desktop est bien lance et reessayez.
        echo.
        pause
        exit /b 1
    )
)

:: 3. Verification du fichier de configuration .env
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creation automatique de votre fichier de configuration .env...
        copy .env.example .env >nul
        echo [SUCCES] Fichier .env initialise avec succes.
    )
)

:: 4. Lecture du port configure (defaut 8000)
set "APP_PORT=8000"
if exist ".env" (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if "%%a"=="APP_PORT" set "APP_PORT=%%b"
    )
)

echo.
echo [1/3] Construction et demarrage du conteneur isole...
docker compose up -d --build

if %errorlevel% neq 0 (
    echo [ERREUR] Echec lors du demarrage avec Docker Compose.
    echo Consultez les logs avec la commande : docker compose logs
    echo.
    pause
    exit /b 1
)

echo [2/3] Verification de la disponibilite du serveur (Port %APP_PORT%)...
timeout /t 3 /nobreak >nul

echo [3/3] Ouverture automatique dans votre navigateur web...
start http://localhost:%APP_PORT%

echo.
echo ===============================================================================
echo   ✅ APPLICATION OPERATIONNELLE SUR : http://localhost:%APP_PORT%
echo   - Pour arreter : docker compose stop
echo   - Pour voir les logs en direct : docker compose logs -f
echo ===============================================================================
echo.
pause
