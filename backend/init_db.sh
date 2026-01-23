#!/bin/bash

# Script shell pour initialiser la base de données

# Activer l'environnement virtuel si il existe
if [ -d "venv" ]; then
    echo "🔌 Activation de l'environnement virtuel..."
    source venv/bin/activate
fi

# Variables d'environnement (optionnel, les valeurs par défaut sont dans init_db.py)
export DB_HOST=${DB_HOST:-"localhost"}
export DB_PORT=${DB_PORT:-"5432"}
export DB_USER=${DB_USER:-"postgres"}
export DB_PASSWORD=${DB_PASSWORD:-"postgres"}
export DB_NAME=${DB_NAME:-"tpkubernetes"}

# Installer les dépendances si nécessaire
if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo "📥 Installation de psycopg2-binary..."
    pip install psycopg2-binary
fi

# Lancer le script d'initialisation
python3 init_db.py

