@echo off
title ProjectMind — FastAPI Server
cd /d C:\AION_APPS\repos\ProjectMind

echo.
echo  ============================================
echo   ProjectMind - Demarrage du serveur
echo   http://localhost:8766
echo   Ctrl+C pour arreter
echo  ============================================
echo.

:: Activer l environnement virtuel
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [WARN] Pas de .venv trouve - utilisation du Python systeme
)

:: Git pull automatique au demarrage (optionnel - commenter si non desire)
:: git pull origin main

:: Lancer uvicorn
uvicorn main:app --reload --port 8766

:: Si uvicorn se ferme, pause pour voir l erreur
echo.
echo [INFO] Serveur arrete.
pause
