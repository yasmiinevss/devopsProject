# DevOps Project - Kubernetes ToDo List

**Auteurs :** Yasmine Mazghi, Rayane Moussa

Ce projet déploie une application ToDo List complète sur Kubernetes (Minikube). L'architecture en micro-services inclut la persistance des données (PostgreSQL), la sécurité (HTTPS/Cert-Manager, Vault), le monitoring (Prometheus/Grafana) et le logging centralisé (OpenSearch/Fluent Bit).

---

## Prérequis

* **Minikube** (Driver Docker recommandé)
* **Kubectl**
* **Helm**
* **Docker**
* **Ressources :** Minimum **6GB de RAM** et **4 CPUs**.

---

## 1. Démarrage & Construction

###     Démarrage du Cluster
Lancez ces commandes dans votre terminal principal :

```bash
minikube start --driver=docker --memory=8192 --cpus=4
minikube addons enable ingress
```
##      IMPORTANT : Le Tunnel Ouvrez un nouveau terminal et lancez cette commande (laissez ce terminal ouvert) :
```bash
sudo minikube tunnel
```

##      Construction des Images Docker
Revenez dans votre terminal principal et construisez les images :
```bash
eval $(minikube docker-env)
docker build -t exam-kubernetes-backend:latest ./backend
docker build -t exam-kubernetes-frontend:latest ./frontend
```
## 2. Déploiement de l'Infrastructure

Vous pouvez copier-coller ce bloc entier pour déployer l'application, la base de données et le monitoring.

```bash
# 1. Base de données
kubectl apply -f kubernetes/db/namespace.yaml
kubectl apply -f kubernetes/db/postgres-secret.yaml
kubectl apply -f kubernetes/db/postgres-pvc.yaml
kubectl apply -f kubernetes/db/postgres-deployment.yaml
kubectl apply -f kubernetes/db/postgres-service.yaml

# 2. Application Todolist (RBAC & Configs)
kubectl apply -f kubernetes/todolist/namespace.yaml
kubectl apply -f kubernetes/todolist/serviceaccount.yaml
kubectl apply -f kubernetes/todolist/role.yaml
kubectl apply -f kubernetes/todolist/rolebinding.yaml
kubectl apply -f kubernetes/todolist/backend-configmap.yaml
kubectl apply -f kubernetes/todolist/backend-secret.yaml
kubectl apply -f kubernetes/todolist/frontend-configmap.yaml

# 3. Déploiements Backend & Frontend
kubectl apply -f kubernetes/todolist/backend-deployment.yaml
kubectl apply -f kubernetes/todolist/backend-service.yaml
kubectl apply -f kubernetes/todolist/frontend-deployment.yaml
kubectl apply -f kubernetes/todolist/frontend-service.yaml
```

##      Initialisation des données
Attendez que les pods soient "Running", puis lancez :
```bash
POD_NAME=$(kubectl get pod -n todolist -l app=backend -o jsonpath="{.items[0].metadata.name}")
kubectl cp resources/init_db.py todolist/$POD_NAME:/tmp/init_db.py
kubectl exec -n todolist $POD_NAME -- python3 /tmp/init_db.py
```

##      Phase 2 : Monitoring (Prometheus & Grafana)
```bash
# Installation de la stack
kubectl apply -f kubernetes/monitoring/namespace.yaml
helm repo add prometheus-community [https://prometheus-community.github.io/helm-charts](https://prometheus-community.github.io/helm-charts)
helm repo update
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring

# Application des moniteurs
kubectl apply -f kubernetes/monitoring/backend-servicemonitor.yaml
kubectl apply -f kubernetes/monitoring/promotheus-rule-backend.yaml
```
## 3. Sécurité & Accès Externe

##      Phase 3 : Vault (Secrets Dynamiques)

```bash
# Installation
helm repo add hashicorp [https://helm.releases.hashicorp.com](https://helm.releases.hashicorp.com)
helm install vault hashicorp/vault -n vault --create-namespace

# Initialisation (Attendre que vault-0 soit Running)
sleep 15
kubectl exec -n vault vault-0 -- vault operator init -key-shares=1 -key-threshold=1 -format=json > cluster-keys.json
VAULT_UNSEAL_KEY=$(cat cluster-keys.json | jq -r ".unseal_keys_b64[0]")
VAULT_ROOT_TOKEN=$(cat cluster-keys.json | jq -r ".root_token")

# Déverrouillage & Configuration
kubectl exec -n vault vault-0 -- vault operator unseal $VAULT_UNSEAL_KEY
kubectl exec -n vault vault-0 -- vault login $VAULT_ROOT_TOKEN
kubectl exec -n vault vault-0 -- vault secrets enable database
```
##      Phase 4 : HTTPS (Cert-Manager & Ingress)
```bash
# Installation Cert-Manager
helm repo add jetstack [https://charts.jetstack.io](https://charts.jetstack.io)
helm install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace --set crds.enabled=true

# Configuration TLS & Ingress
kubectl apply -f kubernetes/cert-manager/issuer.yaml
kubectl apply -f kubernetes/cert-manager/certificate.yaml
kubectl apply -f kubernetes/ingress/ingress.yaml
```

## 4. Logging (OpenSearch & Fluent Bit)

##      Phase 5 : Déploiement Stack Logging

```bash
# 1. OpenSearch
helm repo add opensearch [https://opensearch-project.github.io/helm-charts](https://opensearch-project.github.io/helm-charts)
helm install opensearch opensearch/opensearch -n logging --create-namespace -f resources/values-opensearch.yaml
helm install opensearch-dashboards opensearch/opensearch-dashboards -n logging -f resources/values-opensearch-dashboards.yaml

# 2. Fluent Bit (Configuration Custom)
helm repo add fluent [https://fluent.github.io/helm-charts](https://fluent.github.io/helm-charts)
helm install fluent-bit fluent/fluent-bit -n logging -f kubernetes/logging/values-fluentbit.yaml
```

Accès Logs :

1. Port-forward : kubectl port-forward -n logging svc/opensearch-dashboards 5601:5601

2. URL : http://localhost:5601 (Login: admin / admin)

3. Créer un index pattern todolist*.

## Nettoyage
```bash
mminikube delete
```