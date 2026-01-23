#!/bin/bash

# Script pour lancer le backend FastAPI en local

# Vérifier si un environnement virtuel existe
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel Python..."
    python3 -m venv venv
fi

# Activer l'environnement virtuel
echo "🔌 Activation de l'environnement virtuel..."
source venv/bin/activate

# Installer/updater les dépendances
echo "📥 Installation des dépendances..."
pip install --upgrade pip
pip install -r requirements.txt

# Variables d'environnement (optionnel, les valeurs par défaut sont dans main.py)
export APP_NAME=${APP_NAME:-"tp-kubernetes-backend"}
export APP_VERSION=${APP_VERSION:-"1.0.0"}
export DB_HOST=${DB_HOST:-"localhost"}
export DB_PORT=${DB_PORT:-"5432"}
export DB_USER=${DB_USER:-"postgres"}
export DB_PASSWORD=${DB_PASSWORD:-"postgres"}
export DB_NAME=${DB_NAME:-"tpkubernetes"}

echo "🚀 Démarrage du backend FastAPI..."
echo "📍 Backend disponible sur: http://localhost:8000"
echo "📚 Documentation: http://localhost:8000/docs"
echo "📊 Métriques: http://localhost:8000/metrics"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter"
echo ""

# Lancer uvicorn avec rechargement automatique
uvicorn main:app --reload --host 0.0.0.0 --port 8000

