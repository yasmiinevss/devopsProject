"""
Backend FastAPI pour TP Kubernetes
- Endpoints système (health, ready, metrics)
- API CRUD items
- Observabilité Prometheus
- Création de pods Kubernetes (test ServiceAccount)
"""
import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import psycopg2
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST as OPENMETRICS_CONTENT_TYPE
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

# Variables d'environnement
APP_NAME = os.getenv("APP_NAME", "tp-kubernetes-backend")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "tpkubernetes")

# Métriques Prometheus
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "route", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

http_inflight_requests = Gauge(
    "http_inflight_requests",
    "Number of HTTP requests currently being processed",
    ["route"]
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware pour instrumenter toutes les routes avec Prometheus"""
    
    async def dispatch(self, request: Request, call_next):
        # Template de route (sans paramètres)
        route_template = request.url.path
        # Remplacer les IDs par {id} pour regrouper les métriques
        if "/api/items/" in route_template and len(route_template.split("/")) == 4:
            route_template = "/api/items/{id}"
        
        method = request.method
        route = route_template
        
        # Incrémenter les requêtes en cours
        http_inflight_requests.labels(route=route).inc()
        
        start_time = time.time()
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            status_code = 500
            raise
        finally:
            # Calculer la durée
            duration = time.time() - start_time
            
            # Décrémenter les requêtes en cours
            http_inflight_requests.labels(route=route).dec()
            
            # Enregistrer les métriques
            http_requests_total.labels(
                method=method,
                route=route,
                status=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                route=route
            ).observe(duration)


def get_db_connection():
    """Créer une connexion à PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except Exception as e:
        print(f"Erreur de connexion DB: {e}")
        return None


def init_db():
    """Initialiser la table items si elle n'existe pas"""
    conn = get_db_connection()
    if conn is None:
        print("⚠️  Impossible de se connecter à la DB pour l'initialisation")
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        print("✅ Table 'items' initialisée")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la DB: {e}")
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: init DB au démarrage"""
    print(f"🚀 Démarrage de {APP_NAME} v{APP_VERSION}")
    init_db()
    yield
    print(f"🛑 Arrêt de {APP_NAME}")


# Créer l'application FastAPI
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, restreindre aux origines autorisées
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus middleware (doit être ajouté après CORS)
app.add_middleware(PrometheusMiddleware)


# Modèles Pydantic
class ItemCreate(BaseModel):
    title: str


class ItemUpdate(BaseModel):
    title: str


class Item(BaseModel):
    id: int
    title: str
    created_at: str
    
    class Config:
        from_attributes = True


# ========== ENDPOINTS SYSTÈME ==========

@app.get("/health")
async def health():
    """Liveness probe: toujours 200"""
    return {"status": "healthy", "service": APP_NAME}


@app.get("/ready")
async def ready():
    """Readiness probe: 200 si DB OK, sinon 503"""
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {"status": "ready", "service": APP_NAME}
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=503, detail=f"Database check failed: {str(e)}")


@app.get("/metrics")
async def metrics():
    """Exposition des métriques Prometheus"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/version")
async def version():
    """Retourne la version de l'application"""
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION
    }


@app.get("/api/env")
async def get_env_vars():
    """
    Retourne toutes les variables d'environnement (les sensibles sont masquées)
    Utile pour le debugging et la configuration
    """
    # Liste des mots-clés qui indiquent des variables sensibles
    sensitive_keywords = ['USER', 'PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'CREDENTIAL', 'AUTH', 'SHA256', 'HASH']
    
    env_vars = {}
    for key, value in os.environ.items():
        # Masquer les variables sensibles
        if any(keyword in key.upper() for keyword in sensitive_keywords):
            env_vars[key] = "***"
        else:
            env_vars[key] = value
    
    return env_vars


# ========== API CRUD ITEMS ==========

@app.get("/api/items", response_model=List[Item])
async def get_items():
    """Récupérer tous les items"""
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, created_at FROM items ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        items = [
            Item(
                id=row[0],
                title=row[1],
                created_at=row[2].isoformat() if row[2] else ""
            )
            for row in rows
        ]
        return items
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error fetching items: {str(e)}")


@app.get("/api/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    """Récupérer un item par ID"""
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, created_at FROM items WHERE id = %s", (item_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")
        
        return Item(
            id=row[0],
            title=row[1],
            created_at=row[2].isoformat() if row[2] else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error fetching item: {str(e)}")


@app.post("/api/items", response_model=Item, status_code=201)
async def create_item(item: ItemCreate):
    """Créer un nouvel item"""
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO items (title) VALUES (%s) RETURNING id, title, created_at",
            (item.title,)
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return Item(
            id=row[0],
            title=row[1],
            created_at=row[2].isoformat() if row[2] else ""
        )
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error creating item: {str(e)}")


@app.put("/api/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item: ItemUpdate):
    """Mettre à jour un item"""
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE items SET title = %s WHERE id = %s RETURNING id, title, created_at",
            (item.title, item_id)
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")
        
        return Item(
            id=row[0],
            title=row[1],
            created_at=row[2].isoformat() if row[2] else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error updating item: {str(e)}")


@app.delete("/api/items/{item_id}", status_code=204)
async def delete_item(item_id: int):
    """Supprimer un item"""
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.close()
        raise HTTPException(status_code=500, detail=f"Error deleting item: {str(e)}")


# ========== ENDPOINT TEST ERREUR 500 ==========

@app.get("/api/error")
async def trigger_error():
    """
    Endpoint de test qui retourne intentionnellement une erreur 500
    Utile pour tester les alertes Prometheus et le dashboard Grafana
    """
    raise HTTPException(
        status_code=500,
        detail="Erreur 500 intentionnelle pour tester le monitoring"
    )


@app.post("/api/error")
async def trigger_error_post():
    """
    Endpoint POST de test qui retourne intentionnellement une erreur 500
    """
    raise HTTPException(
        status_code=500,
        detail="Erreur 500 intentionnelle pour tester le monitoring"
    )


# ========== ENDPOINT KUBERNETES (TEST SERVICEACCOUNT) ==========

def get_k8s_client():
    """Initialiser le client Kubernetes (utilise le ServiceAccount du pod)"""
    try:
        # Essayer de charger la config depuis le cluster (ServiceAccount)
        config.load_incluster_config()
    except:
        try:
            # Fallback: config locale (pour développement)
            config.load_kube_config()
        except:
            return None
    return client.CoreV1Api()


@app.post("/api/test-pod")
async def create_test_pod():
    """
    Créer un pod de test dans le namespace 'todolist'
    Permet de tester les permissions du ServiceAccount
    """
    k8s_client = get_k8s_client()
    if k8s_client is None:
        raise HTTPException(
            status_code=503,
            detail="Kubernetes client not available. Make sure the pod has proper ServiceAccount permissions."
        )
    
    namespace = "todolist"
    pod_name = f"test-pod-{int(time.time())}"
    
    # Définition du pod
    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "namespace": namespace,
            "labels": {
                "app": "test-pod",
                "created-by": "backend-api"
            }
        },
        "spec": {
            "containers": [
                {
                    "name": "test-container",
                    "image": "busybox:latest",
                    "command": ["sleep", "3600"],
                    "resources": {
                        "requests": {
                            "cpu": "50m",
                            "memory": "64Mi"
                        },
                        "limits": {
                            "cpu": "100m",
                            "memory": "128Mi"
                        }
                    }
                }
            ],
            "restartPolicy": "Never"
        }
    }
    
    try:
        # Créer le pod
        pod = k8s_client.create_namespaced_pod(
            namespace=namespace,
            body=pod_manifest
        )
        return {
            "status": "success",
            "message": f"Pod '{pod_name}' created successfully",
            "pod_name": pod_name,
            "namespace": namespace,
            "pod_uid": pod.metadata.uid
        }
    except ApiException as e:
        if e.status == 403:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied. ServiceAccount needs 'pods/create' permission in namespace '{namespace}'. Check Role and RoleBinding."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Error creating pod: {e.reason} - {e.body}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

