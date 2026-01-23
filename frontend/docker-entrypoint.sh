#!/bin/sh
set -e

# Remplacer la variable BACKEND_URL dans le template Nginx
# Par défaut, utilise le service Kubernetes "backend" si non défini
export BACKEND_URL="${BACKEND_URL:-http://backend:8000}"
envsubst '${BACKEND_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# Démarrer Nginx
exec "$@"

