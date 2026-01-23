import { useState, useEffect } from 'react'
import './App.css'

// Configuration API
// Si VITE_API_BASE_URL est vide ou non définie, utiliser un chemin relatif
// Cela permet au proxy Nginx de rediriger vers le backend (sans Ingress)
// ou à l'Ingress de gérer le routage (avec Ingress)
// Sinon utiliser la valeur configurée (pour développement local)
const viteApiUrl = import.meta.env.VITE_API_BASE_URL
const API_BASE_URL = (!viteApiUrl || viteApiUrl === '' || viteApiUrl === 'undefined') 
  ? ''  // Chemin relatif pour proxy Nginx ou Ingress
  : viteApiUrl || 'http://localhost:8000'  // Valeur configurée ou défaut dev

interface Item {
  id: number
  title: string
  created_at: string
}

interface HealthStatus {
  health: 'healthy' | 'unhealthy'
  ready: 'ready' | 'not-ready'
  version?: string
}

function App() {
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [healthStatus, setHealthStatus] = useState<HealthStatus>({
    health: 'unhealthy',
    ready: 'not-ready'
  })
  const [newItemTitle, setNewItemTitle] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [podCreating, setPodCreating] = useState(false)
  const [podMessage, setPodMessage] = useState<string | null>(null)
  const [showEnvVars, setShowEnvVars] = useState(false)
  const [backendEnvVars, setBackendEnvVars] = useState<Record<string, any> | null>(null)

  // Charger les items
  const fetchItems = async () => {
    try {
      setError(null)
      const response = await fetch(`${API_BASE_URL}/api/items`)
      if (!response.ok) {
        throw new Error(`Erreur ${response.status}: ${response.statusText}`)
      }
      const data = await response.json()
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors du chargement des items')
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  // Vérifier l'état de santé
  const checkHealth = async () => {
    try {
      // Health check
      const healthRes = await fetch(`${API_BASE_URL}/health`)
      const healthOk = healthRes.ok

      // Ready check
      let readyOk = false
      try {
        const readyRes = await fetch(`${API_BASE_URL}/ready`)
        readyOk = readyRes.ok
      } catch {
        readyOk = false
      }

      // Version
      let version: string | undefined
      try {
        const versionRes = await fetch(`${API_BASE_URL}/version`)
        if (versionRes.ok) {
          const versionData = await versionRes.json()
          version = versionData.version
        }
      } catch {
        // Ignore version errors
      }

      setHealthStatus({
        health: healthOk ? 'healthy' : 'unhealthy',
        ready: readyOk ? 'ready' : 'not-ready',
        version
      })
    } catch (err) {
      setHealthStatus({
        health: 'unhealthy',
        ready: 'not-ready'
      })
    }
  }

  // Charger les données au montage et vérifier la santé
  useEffect(() => {
    fetchItems()
    checkHealth()
    // Note: Les probes Kubernetes (liveness/readiness) gèrent déjà la santé du backend
    // Pas besoin de polling côté frontend
  }, [])

  // Charger les variables d'environnement du backend quand on ouvre le volet
  useEffect(() => {
    if (showEnvVars) {
      fetchBackendEnvVars()
    }
  }, [showEnvVars])

  // Récupérer toutes les variables d'environnement du frontend (build-time)
  const frontendEnvVars: Record<string, any> = {}
  // Récupérer toutes les propriétés de import.meta.env
  Object.keys(import.meta.env).forEach(key => {
    frontendEnvVars[key] = import.meta.env[key]
  })

  // Créer un item
  const handleCreateItem = async () => {
    if (!newItemTitle.trim()) return

    try {
      setError(null)
      const response = await fetch(`${API_BASE_URL}/api/items`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: newItemTitle }),
      })

      if (!response.ok) {
        throw new Error(`Erreur ${response.status}: ${response.statusText}`)
      }

      setNewItemTitle('')
      await fetchItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la création')
    }
  }

  // Démarrer l'édition
  const startEdit = (item: Item) => {
    setEditingId(item.id)
    setEditingTitle(item.title)
  }

  // Annuler l'édition
  const cancelEdit = () => {
    setEditingId(null)
    setEditingTitle('')
  }

  // Mettre à jour un item
  const handleUpdateItem = async (id: number) => {
    if (!editingTitle.trim()) return

    try {
      setError(null)
      const response = await fetch(`${API_BASE_URL}/api/items/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: editingTitle }),
      })

      if (!response.ok) {
        throw new Error(`Erreur ${response.status}: ${response.statusText}`)
      }

      setEditingId(null)
      setEditingTitle('')
      await fetchItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la mise à jour')
    }
  }

  // Supprimer un item
  const handleDeleteItem = async (id: number) => {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cet item ?')) return

    try {
      setError(null)
      const response = await fetch(`${API_BASE_URL}/api/items/${id}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error(`Erreur ${response.status}: ${response.statusText}`)
      }

      await fetchItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la suppression')
    }
  }

  // Récupérer les variables d'environnement du backend
  const fetchBackendEnvVars = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/env`)
      if (response.ok) {
        const data = await response.json()
        setBackendEnvVars(data)
      }
    } catch (err) {
      // Ignore errors
    }
  }

  // Créer un pod de test (test ServiceAccount)
  const handleCreateTestPod = async () => {
    try {
      setPodCreating(true)
      setPodMessage(null)
      setError(null)
      
      const response = await fetch(`${API_BASE_URL}/api/test-pod`, {
        method: 'POST',
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || `Erreur ${response.status}: ${response.statusText}`)
      }

      setPodMessage(`✅ Pod créé avec succès: ${data.pod_name} dans le namespace ${data.namespace}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la création du pod')
      setPodMessage(null)
    } finally {
      setPodCreating(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>TP Kubernetes - Items Manager</h1>
        <div className="health-status">
          <div className="status-item">
            <span className="status-label">Health:</span>
            <span className={`status-badge ${healthStatus.health}`}>
              {healthStatus.health === 'healthy' ? '✓' : '✗'} {healthStatus.health}
            </span>
          </div>
          <div className="status-item">
            <span className="status-label">Ready:</span>
            <span className={`status-badge ${healthStatus.ready}`}>
              {healthStatus.ready === 'ready' ? '✓' : '✗'} {healthStatus.ready}
            </span>
          </div>
          {healthStatus.version && (
            <div className="status-item">
              <span className="status-label">Version:</span>
              <span className="version-badge">{healthStatus.version}</span>
            </div>
          )}
          <div className="status-item">
            <button 
              onClick={() => setShowEnvVars(!showEnvVars)}
              className="btn-env-toggle"
            >
              {showEnvVars ? '🔽' : '▶️'} Variables d'environnement
            </button>
          </div>
        </div>
      </header>

      {showEnvVars && (
        <div className="env-vars-panel">
          <div className="env-warning">
            <strong>⚠️ Note de sécurité :</strong> Les variables sensibles (secrets) ne sont pas exposées ici pour des raisons de sécurité. 
            Toute personne ayant les permissions pour exécuter <code>kubectl exec</code> dans le pod peut néanmoins récupérer toutes les variables d'environnement, y compris les secrets.
            <br />Il faut donc faire attention aux accès qu'on donne
          </div>
          <div className="env-section">
            <h3>Frontend (Build-time)</h3>
            <div className="env-vars-list">
              {Object.entries(frontendEnvVars).map(([key, value]) => (
                <div key={key} className="env-var-item">
                  <span className="env-var-key">{key}:</span>
                  <span className="env-var-value">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="env-section">
            <h3>Backend (Runtime)</h3>
            {backendEnvVars ? (
              <div className="env-vars-list">
                {Object.entries(backendEnvVars).map(([key, value]) => (
                  <div key={key} className="env-var-item">
                    <span className="env-var-key">{key}:</span>
                    <span className="env-var-value">{String(value)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="env-loading">Chargement...</div>
            )}
          </div>
        </div>
      )}

      <main className="main">
        <div className="stats">
          <div className="stat-card">
            <span className="stat-label">Nombre total d'items</span>
            <span className="stat-value">{items.length}</span>
          </div>
        </div>

        <div className="test-pod-section">
          <h2>Test ServiceAccount</h2>
          <p className="test-pod-description">
            Créer un pod de test dans le namespace <strong>todolist</strong> pour vérifier les permissions du ServiceAccount.
          </p>
          <button 
            onClick={handleCreateTestPod} 
            className="btn btn-primary"
            disabled={podCreating}
          >
            {podCreating ? 'Création en cours...' : '🚀 Créer un pod de test'}
          </button>
          {podMessage && (
            <div className="pod-message success">
              {podMessage}
            </div>
          )}
        </div>

        {error && (
          <div className="error-banner">
            <strong>Erreur:</strong> {error}
          </div>
        )}

        <div className="add-item-section">
          <h2>Ajouter un item</h2>
          <div className="add-item-form">
            <input
              type="text"
              value={newItemTitle}
              onChange={(e) => setNewItemTitle(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleCreateItem()}
              placeholder="Titre de l'item..."
              className="input"
            />
            <button onClick={handleCreateItem} className="btn btn-primary">
              Ajouter
            </button>
          </div>
        </div>

        <div className="items-section">
          <h2>Liste des items</h2>
          {loading ? (
            <div className="loading">Chargement...</div>
          ) : items.length === 0 ? (
            <div className="empty-state">Aucun item pour le moment</div>
          ) : (
            <div className="items-list">
              {items.map((item) => (
                <div key={item.id} className="item-card">
                  {editingId === item.id ? (
                    <div className="item-edit">
                      <input
                        type="text"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') handleUpdateItem(item.id)
                          if (e.key === 'Escape') cancelEdit()
                        }}
                        className="input"
                        autoFocus
                      />
                      <div className="item-actions">
                        <button
                          onClick={() => handleUpdateItem(item.id)}
                          className="btn btn-success"
                        >
                          ✓ Sauvegarder
                        </button>
                        <button onClick={cancelEdit} className="btn btn-secondary">
                          ✗ Annuler
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="item-content">
                        <h3 className="item-title">{item.title}</h3>
                        <p className="item-date">
                          Créé le: {new Date(item.created_at).toLocaleString('fr-FR')}
                        </p>
                      </div>
                      <div className="item-actions">
                        <button
                          onClick={() => startEdit(item)}
                          className="btn btn-secondary"
                        >
                          ✏️ Modifier
                        </button>
                        <button
                          onClick={() => handleDeleteItem(item.id)}
                          className="btn btn-danger"
                        >
                          🗑️ Supprimer
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App

