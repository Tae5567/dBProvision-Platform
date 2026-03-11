'use client'

import { useState, useEffect } from 'react'
import { api } from '@/lib/api'

export default function Dashboard() {
  const [overview, setOverview] = useState<any>(null)
  const [databases, setDatabases] = useState<any[]>([])
  const [activeTab, setActiveTab] = useState<'databases' | 'migrations' | 'backups' | 'monitoring'>('databases')
  const [showProvisionForm, setShowProvisionForm] = useState(false)
  const [terminalLines, setTerminalLines] = useState<string[]>([
    '$ dbprovision v1.0.0 initialized',
    '$ connecting to management cluster...',
    '$ fleet status loaded',
    '$ ready',
  ])

  const addTerminalLine = (line: string) => {
    setTerminalLines(prev => [...prev.slice(-50), `$ ${line}`])
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 15000)
    return () => clearInterval(interval)
  }, [])

  async function loadData() {
    try {
      const [ov, dbs] = await Promise.all([
        api.getFleetOverview(),
        api.getDatabases()
      ])
      setOverview(ov)
      setDatabases(dbs)
    } catch (e) {
      addTerminalLine(`error: failed to load data — ${e}`)
    }
  }

  const statusColor = (status: string) => ({
    active: 'text-green-400',
    provisioning: 'text-yellow-400 animate-pulse',
    error: 'text-red-400',
    pending: 'text-blue-400',
    migrating: 'text-cyan-400 animate-pulse',
    backing_up: 'text-purple-400',
    deprovisioned: 'text-gray-500',
  }[status] || 'text-gray-400')

  const envBadge = (env: string) => ({
    prod: 'bg-red-900/50 text-red-300 border border-red-700',
    staging: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700',
    dev: 'bg-blue-900/50 text-blue-300 border border-blue-700',
  }[env] || 'bg-gray-800 text-gray-300')

  return (
    <div className="min-h-screen bg-gray-950 text-green-400 font-mono flex flex-col">
      
      {/* Header */}
      <header className="border-b border-green-900/50 bg-black/40 backdrop-blur-sm px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-green-300 text-lg font-bold tracking-widest">
              ▶ DBPROVISION
            </span>
            <span className="text-green-800 text-xs">v1.0.0</span>
          </div>
          <div className="flex items-center gap-6 text-xs text-green-600">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              LIVE
            </span>
            <span>CLUSTER: us-east-1</span>
            <span>{new Date().toISOString().slice(0, 19).replace('T', ' ')} UTC</span>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        
        {/* Sidebar */}
        <aside className="w-48 bg-black/30 border-r border-green-900/40 flex flex-col py-4 px-3 gap-1 shrink-0">
          {[
            { id: 'databases', label: '⬡ DATABASES' },
            { id: 'migrations', label: '⟳ MIGRATIONS' },
            { id: 'backups', label: '◈ BACKUPS' },
            { id: 'monitoring', label: '◉ MONITORING' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`text-left text-xs py-2 px-3 rounded transition-all ${
                activeTab === tab.id
                  ? 'bg-green-900/40 text-green-300'
                  : 'text-green-700 hover:text-green-500 hover:bg-green-900/20'
              }`}
            >
              {tab.label}
            </button>
          ))}
          
          <div className="mt-auto pt-4 border-t border-green-900/30">
            <div className="text-xs text-green-800 px-3 space-y-1">
              <div>TOTAL DBS</div>
              <div className="text-2xl text-green-400">{overview?.total_databases ?? '—'}</div>
              <div className="mt-2">MONTHLY</div>
              <div className="text-green-300">
                ${overview?.total_monthly_cost?.toFixed(2) ?? '—'}
              </div>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto p-6 space-y-4">
          
          {/* Fleet overview */}
          {overview && (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: 'ACTIVE', value: overview.active, color: 'text-green-400' },
                { label: 'PROVISIONING', value: overview.provisioning, color: 'text-yellow-400' },
                { label: 'ERRORS', value: overview.errored, color: 'text-red-400' },
                { label: 'COST/MO', value: `$${overview.total_monthly_cost.toFixed(0)}`, color: 'text-cyan-400' },
              ].map(stat => (
                <div key={stat.label} className="bg-black/40 border border-green-900/40 rounded p-3">
                  <div className="text-xs text-green-700">{stat.label}</div>
                  <div className={`text-2xl font-bold mt-1 ${stat.color}`}>{stat.value}</div>
                </div>
              ))}
            </div>
          )}

          {/* Tab content */}
          {activeTab === 'databases' && (
            <DatabasesTab
              databases={databases}
              onProvision={() => setShowProvisionForm(true)}
              onAction={addTerminalLine}
              statusColor={statusColor}
              envBadge={envBadge}
            />
          )}
          {activeTab === 'migrations' && (
            <MigrationsTab onAction={addTerminalLine} />
          )}
          {activeTab === 'monitoring' && (
            <MonitoringTab databases={databases} onAction={addTerminalLine} />
          )}
          {activeTab === 'backups' && (
            <BackupsTab databases={databases} onAction={addTerminalLine} />
          )}
        </main>

        {/* Terminal pane */}
        <aside className="w-72 bg-black border-l border-green-900/40 flex flex-col">
          <div className="border-b border-green-900/40 px-4 py-2 text-xs text-green-700">
            ▸ ACTIVITY LOG
          </div>
          <div className="flex-1 overflow-auto p-3 space-y-1">
            {terminalLines.map((line, i) => (
              <div key={i} className="text-xs text-green-600 leading-relaxed">
                {line}
              </div>
            ))}
          </div>
        </aside>
      </div>

      {/* Provision modal */}
      {showProvisionForm && (
        <ProvisionModal
          onClose={() => setShowProvisionForm(false)}
          onSuccess={() => {
            setShowProvisionForm(false)
            loadData()
            addTerminalLine('provisioning request submitted')
          }}
        />
      )}
    </div>
  )
}

// --- Sub-components ---

function DatabasesTab({ databases, onProvision, onAction, statusColor, envBadge }: any) {
  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-xs text-green-700">
          {databases.length} database(s) total
        </span>
        <button
          onClick={onProvision}
          className="text-xs bg-green-900/40 border border-green-700/50 text-green-300 px-4 py-1.5 rounded hover:bg-green-800/40 transition-colors"
        >
          + PROVISION NEW
        </button>
      </div>
      
      <div className="space-y-2">
        {databases.map((db: any) => (
          <div
            key={db.id}
            className="bg-black/40 border border-green-900/30 rounded p-4 hover:border-green-700/50 transition-colors"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <span className="text-green-300 font-bold">{db.tenant_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded font-mono ${envBadge(db.environment)}`}>
                    {db.environment}
                  </span>
                  <span className={`text-xs font-bold ${statusColor(db.status)}`}>
                    ● {db.status.toUpperCase()}
                  </span>
                </div>
                <div className="text-xs text-green-700 mt-1 space-x-4">
                  <span>{db.db_identifier}</span>
                  {db.db_host && <span>{db.db_host}:{db.db_port}</span>}
                  <span>tier: {db.tier}</span>
                  <span>v{db.schema_version}</span>
                </div>
                {db.status_message && (
                  <div className="text-xs text-green-800 mt-1">{db.status_message}</div>
                )}
              </div>
              <div className="text-right text-xs text-green-700">
                <div className="text-green-400">${db.monthly_cost_estimate.toFixed(2)}/mo</div>
                <div className="mt-1">{db.team}</div>
              </div>
            </div>
          </div>
        ))}
        
        {databases.length === 0 && (
          <div className="text-center py-12 text-green-800 text-sm">
            no databases found. provision one to get started.
          </div>
        )}
      </div>
    </div>
  )
}

function MigrationsTab({ onAction }: any) {
  const [migrations, setMigrations] = useState<any[]>([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', version: '', description: '', up_sql: '', down_sql: '', created_by: 'admin' })
  const [bulkEnv, setBulkEnv] = useState('staging')

  useEffect(() => {
    api.getMigrations().then(setMigrations).catch(console.error)
  }, [])

  async function handleCreate() {
    try {
      await api.createMigration({ ...form, version: parseInt(form.version) })
      onAction(`created migration: ${form.name}`)
      setShowForm(false)
      const updated = await api.getMigrations()
      setMigrations(updated)
    } catch (e) {
      onAction(`error creating migration: ${e}`)
    }
  }

  async function handleBulkRun(migrationId: string) {
    try {
      const job = await api.runBulkMigration({
        migration_id: migrationId,
        target_env: bulkEnv,
        created_by: 'admin'
      })
      onAction(`bulk migration job created: ${job.job_id}`)
    } catch (e) {
      onAction(`error: ${e}`)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-xs text-green-700">{migrations.length} migration(s)</span>
        <div className="flex gap-2">
          <select
            value={bulkEnv}
            onChange={e => setBulkEnv(e.target.value)}
            className="text-xs bg-black border border-green-900/50 text-green-400 px-2 py-1 rounded"
          >
            <option value="all">all envs</option>
            <option value="prod">prod</option>
            <option value="staging">staging</option>
            <option value="dev">dev</option>
          </select>
          <button
            onClick={() => setShowForm(true)}
            className="text-xs bg-green-900/40 border border-green-700/50 text-green-300 px-4 py-1.5 rounded hover:bg-green-800/40 transition-colors"
          >
            + NEW MIGRATION
          </button>
        </div>
      </div>

      {showForm && (
        <div className="bg-black/60 border border-green-900/50 rounded p-4 space-y-3">
          <div className="text-xs text-green-500 font-bold">NEW MIGRATION</div>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="migration name"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              className="bg-black border border-green-900/50 text-green-300 text-xs px-3 py-2 rounded"
            />
            <input
              placeholder="version (integer)"
              value={form.version}
              onChange={e => setForm({ ...form, version: e.target.value })}
              className="bg-black border border-green-900/50 text-green-300 text-xs px-3 py-2 rounded"
            />
          </div>
          <textarea
            placeholder="UP SQL (migration)"
            value={form.up_sql}
            onChange={e => setForm({ ...form, up_sql: e.target.value })}
            rows={5}
            className="w-full bg-black border border-green-900/50 text-green-300 text-xs px-3 py-2 rounded font-mono"
          />
          <textarea
            placeholder="DOWN SQL (rollback) — optional"
            value={form.down_sql}
            onChange={e => setForm({ ...form, down_sql: e.target.value })}
            rows={3}
            className="w-full bg-black border border-green-900/50 text-green-300 text-xs px-3 py-2 rounded font-mono"
          />
          <div className="flex gap-2">
            <button onClick={handleCreate} className="text-xs bg-green-900/40 border border-green-700/50 text-green-300 px-4 py-1.5 rounded hover:bg-green-800/40">
              CREATE
            </button>
            <button onClick={() => setShowForm(false)} className="text-xs text-green-700 hover:text-green-500">
              cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {migrations.map((m: any) => (
          <div key={m.id} className="bg-black/40 border border-green-900/30 rounded p-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-green-300 text-sm">{m.name}</span>
                <span className="text-green-700 text-xs ml-3">v{m.version}</span>
                {m.description && (
                  <div className="text-xs text-green-800 mt-0.5">{m.description}</div>
                )}
                <div className="text-xs text-green-900 mt-1">
                  checksum: {m.checksum?.slice(0, 16)}... · by {m.created_by}
                </div>
              </div>
              <button
                onClick={() => handleBulkRun(m.id)}
                className="text-xs bg-cyan-900/40 border border-cyan-700/50 text-cyan-300 px-3 py-1 rounded hover:bg-cyan-800/40"
              >
                RUN → {bulkEnv}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function MonitoringTab({ databases, onAction }: any) {
  const [selectedDb, setSelectedDb] = useState<string>('')
  const [health, setHealth] = useState<any>(null)
  const [slowQueries, setSlowQueries] = useState<any[]>([])

  const activeDbs = databases.filter((d: any) => d.status === 'active')

  async function loadMonitoring(dbId: string) {
    setSelectedDb(dbId)
    try {
      const [h, sq] = await Promise.all([
        api.getHealth(dbId),
        api.getSlowQueries(dbId)
      ])
      setHealth(h)
      setSlowQueries(sq)
    } catch (e) {
      onAction(`error loading monitoring: ${e}`)
    }
  }

  return (
    <div className="space-y-4">
      <select
        value={selectedDb}
        onChange={e => loadMonitoring(e.target.value)}
        className="text-xs bg-black border border-green-900/50 text-green-400 px-3 py-2 rounded w-full"
      >
        <option value="">-- select database --</option>
        {activeDbs.map((db: any) => (
          <option key={db.id} value={db.id}>{db.tenant_name} ({db.environment})</option>
        ))}
      </select>

      {health && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <HealthCard label="CONNECTIONS" value={`${health.connections.active}/${health.connections.max_connections}`} ok={health.connections.active / health.connections.max_connections < 0.8} />
            <HealthCard label="CACHE HIT %" value={`${health.cache_hit_ratio}%`} ok={health.cache_hit_ratio > 95} />
            <HealthCard label="WAITING LOCKS" value={health.waiting_locks} ok={health.waiting_locks < 5} />
          </div>
          
          <div className="bg-black/40 border border-green-900/30 rounded p-3">
            <div className="text-xs text-green-700 mb-2">DATABASE SIZE</div>
            <div className="text-green-300">{health.storage.size_pretty}</div>
            {health.replication_lag_seconds != null && (
              <div className="text-xs text-green-700 mt-2">
                Replication lag: {health.replication_lag_seconds.toFixed(1)}s
              </div>
            )}
          </div>
        </div>
      )}

      {slowQueries.length > 0 && (
        <div className="bg-black/40 border border-green-900/30 rounded p-3">
          <div className="text-xs text-green-700 mb-2">TOP SLOW QUERIES (avg &gt; 1s)</div>
          <div className="space-y-2">
            {slowQueries.slice(0, 5).map((q, i) => (
              <div key={i} className="text-xs border-t border-green-900/20 pt-2">
                <div className="flex justify-between text-green-600">
                  <span>{q.avg_time_ms}ms avg</span>
                  <span>{q.calls} calls</span>
                  <span>{q.cache_hit_pct}% cache</span>
                </div>
                <div className="text-green-800 mt-1 truncate">{q.query?.slice(0, 100)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function HealthCard({ label, value, ok }: { label: string; value: any; ok: boolean }) {
  return (
    <div className={`bg-black/40 border rounded p-3 ${ok ? 'border-green-900/30' : 'border-red-900/50'}`}>
      <div className="text-xs text-green-700">{label}</div>
      <div className={`text-xl font-bold mt-1 ${ok ? 'text-green-400' : 'text-red-400'}`}>{value}</div>
    </div>
  )
}

function BackupsTab({ databases, onAction }: any) {
  const [selectedDb, setSelectedDb] = useState<string>('')
  const [backups, setBackups] = useState<any[]>([])

  const activeDbs = databases.filter((d: any) => d.status === 'active')

  async function loadBackups(dbId: string) {
    setSelectedDb(dbId)
    const bkps = await api.getBackups(dbId)
    setBackups(bkps)
  }

  async function triggerBackup() {
    if (!selectedDb) return
    await api.createBackup(selectedDb, 'manual')
    onAction(`backup initiated for ${selectedDb}`)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <select
          value={selectedDb}
          onChange={e => loadBackups(e.target.value)}
          className="text-xs bg-black border border-green-900/50 text-green-400 px-3 py-2 rounded flex-1"
        >
          <option value="">-- select database --</option>
          {activeDbs.map((db: any) => (
            <option key={db.id} value={db.id}>{db.tenant_name} ({db.environment})</option>
          ))}
        </select>
        {selectedDb && (
          <button onClick={triggerBackup} className="text-xs bg-purple-900/40 border border-purple-700/50 text-purple-300 px-4 py-1.5 rounded hover:bg-purple-800/40">
            + SNAPSHOT NOW
          </button>
        )}
      </div>

      <div className="space-y-2">
        {backups.map((b: any) => (
          <div key={b.id} className="bg-black/40 border border-green-900/30 rounded p-3">
            <div className="flex justify-between text-xs">
              <div>
                <span className={`font-bold ${b.status === 'completed' ? 'text-green-400' : b.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}`}>
                  ● {b.status}
                </span>
                <span className="text-green-700 ml-3">{b.backup_type}</span>
              </div>
              <div className="text-green-700">
                {b.size_bytes ? `${(b.size_bytes / 1024 / 1024 / 1024).toFixed(1)} GB` : '—'}
              </div>
            </div>
            <div className="text-xs text-green-800 mt-1">
              {b.rds_snapshot_id} · {new Date(b.created_at).toLocaleString()}
            </div>
            {b.expires_at && (
              <div className="text-xs text-green-900 mt-0.5">
                expires: {new Date(b.expires_at).toLocaleDateString()}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function ProvisionModal({ onClose, onSuccess }: any) {
  const [form, setForm] = useState({
    tenant_id: '', tenant_name: '', environment: 'dev',
    db_name: '', owner: '', team: '', tier: 'micro', multi_az: false
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    setLoading(true)
    setError('')
    try {
      await api.provisionDatabase(form)
      onSuccess()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const field = (placeholder: string, key: keyof typeof form, type = 'text') => (
    <input
      type={type}
      placeholder={placeholder}
      value={form[key] as string}
      onChange={e => setForm({ ...form, [key]: e.target.value })}
      className="bg-black border border-green-900/50 text-green-300 text-xs px-3 py-2 rounded placeholder-green-900"
    />
  )

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-gray-950 border border-green-800/60 rounded-lg p-6 w-[480px] space-y-4">
        <div className="flex justify-between items-center">
          <span className="text-green-300 font-bold tracking-wide">PROVISION DATABASE</span>
          <button onClick={onClose} className="text-green-800 hover:text-green-600 text-xs">✕ close</button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {field('tenant_id (e.g. acme-corp)', 'tenant_id')}
          {field('tenant_name (display)', 'tenant_name')}
          {field('db_name', 'db_name')}
          {field('owner (email)', 'owner')}
          {field('team name', 'team')}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <select value={form.environment} onChange={e => setForm({ ...form, environment: e.target.value })}
            className="bg-black border border-green-900/50 text-green-300 text-xs px-3 py-2 rounded">
            <option value="dev">dev</option>
            <option value="staging">staging</option>
            <option value="prod">prod</option>
          </select>
          <select value={form.tier} onChange={e => setForm({ ...form, tier: e.target.value })}
            className="bg-black border border-green-900/50 text-green-300 text-xs px-3 py-2 rounded">
            <option value="micro">micro — $12/mo</option>
            <option value="small">small — $25/mo</option>
            <option value="medium">medium — $50/mo</option>
            <option value="large">large — $175/mo</option>
          </select>
        </div>

        <label className="flex items-center gap-2 text-xs text-green-700">
          <input type="checkbox" checked={form.multi_az}
            onChange={e => setForm({ ...form, multi_az: e.target.checked })}
            className="accent-green-500" />
          Enable Multi-AZ (high availability)
        </label>

        {error && <div className="text-xs text-red-400 bg-red-900/20 border border-red-900/40 rounded p-2">{error}</div>}

        <div className="flex gap-3 pt-2">
          <button onClick={handleSubmit} disabled={loading}
            className="flex-1 bg-green-900/50 border border-green-700/60 text-green-300 text-xs py-2 rounded hover:bg-green-800/50 disabled:opacity-50">
            {loading ? 'PROVISIONING...' : '▶ PROVISION'}
          </button>
          <button onClick={onClose} className="text-xs text-green-800 hover:text-green-600 px-4">
            cancel
          </button>
        </div>
      </div>
    </div>
  )
}