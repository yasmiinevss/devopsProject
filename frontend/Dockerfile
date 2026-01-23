# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copier les fichiers de dépendances
COPY package.json package-lock.json* ./

# Installer les dépendances
RUN npm ci

# Copier le code source
COPY . .

# Argument pour VITE_API_BASE_URL (build-time)
# Par défaut vide pour Kubernetes Ingress, peut être surchargé pour dev
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build de l'application
RUN npm run build

# Stage 2: Production avec Nginx
FROM nginx:alpine

# Installer envsubst pour remplacer les variables d'environnement
RUN apk add --no-cache gettext

# Copier les fichiers buildés
COPY --from=builder /app/dist /usr/share/nginx/html

# Copier le template de configuration Nginx
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Script de démarrage pour remplacer BACKEND_URL et démarrer Nginx
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Exposer le port
EXPOSE 80

# Point d'entrée personnalisé
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]

