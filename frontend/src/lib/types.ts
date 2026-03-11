export type DatabaseStatus = 
  | 'pending' | 'provisioning' | 'active' 
  | 'migrating' | 'backing_up' | 'scaling' 
  | 'error' | 'deprovisioned'

export type DatabaseTier = 'micro' | 'small' | 'medium' | 'large' | 'xlarge'

export interface TenantDatabase {
  id: string
  tenant_id: string
  tenant_name: string
  environment: 'prod' | 'staging' | 'dev'
  db_identifier: string
  db_host?: string
  db_port: number
  db_name: string
  status: DatabaseStatus
  status_message?: string
  tier: DatabaseTier
  schema_version: number
  monthly_cost_estimate: number
  multi_az: boolean
  owner: string
  team: string
  created_at: string
  updated_at?: string
}

export interface Migration {
  id: string
  name: string
  version: number
  description?: string
  checksum: string
  created_at: string
  created_by: string
}

export interface BulkMigrationJob {
  id: string
  migration_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  total_databases: number
  completed: number
  failed: number
  results: Record<string, any>
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface Backup {
  id: string
  tenant_db_id: string
  backup_type: 'automated' | 'manual' | 'pre_migration' | 'snapshot'
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'expired'
  rds_snapshot_id?: string
  size_bytes?: number
  started_at?: string
  completed_at?: string
  expires_at?: string
  created_at: string
}

export interface DatabaseHealth {
  connections: {
    total: number
    active: number
    idle: number
    idle_in_tx: number
    max_connections: number
  }
  storage: {
    size_bytes: number
    size_pretty: string
  }
  replication_lag_seconds?: number
  cache_hit_ratio: number
  waiting_locks: number
  healthy: boolean
}

export interface FleetOverview {
  total_databases: number
  active: number
  errored: number
  provisioning: number
  total_monthly_cost: number
}