const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Databases
  getDatabases: (params?: { environment?: string; team?: string; status?: string }) =>
    apiFetch<any[]>(`/api/v1/databases?${new URLSearchParams(params as any)}`),
  
  getDatabase: (id: string) =>
    apiFetch<any>(`/api/v1/databases/${id}`),
  
  provisionDatabase: (data: any) =>
    apiFetch<any>('/api/v1/databases/provision', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
  
  deprovisionDatabase: (id: string, force = false) =>
    apiFetch<any>(`/api/v1/databases/${id}?force=${force}`, { method: 'DELETE' }),

  // Migrations
  getMigrations: () => apiFetch<any[]>('/api/v1/migrations'),
  
  createMigration: (data: any) =>
    apiFetch<any>('/api/v1/migrations', { method: 'POST', body: JSON.stringify(data) }),
  
  runBulkMigration: (data: any) =>
    apiFetch<any>('/api/v1/migrations/bulk', { method: 'POST', body: JSON.stringify(data) }),
  
  getBulkJob: (jobId: string) =>
    apiFetch<any>(`/api/v1/migrations/bulk/${jobId}`),

  // Backups
  getBackups: (dbId: string) => apiFetch<any[]>(`/api/v1/backups/${dbId}`),
  
  createBackup: (dbId: string, type = 'manual') =>
    apiFetch<any>(`/api/v1/backups/${dbId}/snapshot?backup_type=${type}`, { method: 'POST' }),
  
  restoreBackup: (backupId: string, targetId: string) =>
    apiFetch<any>(`/api/v1/backups/${backupId}/restore?target_identifier=${targetId}`, { method: 'POST' }),

  // Monitoring
  getHealth: (dbId: string) => apiFetch<any>(`/api/v1/monitoring/${dbId}/health`),
  getSlowQueries: (dbId: string, thresholdMs = 1000) =>
    apiFetch<any[]>(`/api/v1/monitoring/${dbId}/slow-queries?threshold_ms=${thresholdMs}`),
  getIndexSuggestions: (dbId: string) =>
    apiFetch<any[]>(`/api/v1/monitoring/${dbId}/index-suggestions`),
  getFleetOverview: () => apiFetch<any>('/api/v1/monitoring/overview'),

  // Access
  grantPermissions: (dbId: string, data: any) =>
    apiFetch<any>(`/api/v1/access/${dbId}/grant`, { method: 'POST', body: JSON.stringify(data) }),
  revokePermissions: (dbId: string, data: any) =>
    apiFetch<any>(`/api/v1/access/${dbId}/revoke`, { method: 'POST', body: JSON.stringify(data) }),
  listUsers: (dbId: string) => apiFetch<any[]>(`/api/v1/access/${dbId}/users`),
}