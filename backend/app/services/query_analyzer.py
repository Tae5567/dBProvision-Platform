import asyncpg
from typing import List, Dict
import logging

log = logging.getLogger(__name__)

class QueryAnalyzer:
    
    async def get_slow_queries(
        self, 
        host: str, port: int, db_name: str, 
        username: str, password: str,
        threshold_ms: float = 1000.0,
        limit: int = 20
    ) -> List[Dict]:
        """Fetch slow queries from pg_stat_statements."""
        
        conn = await asyncpg.connect(
            host=host, port=port, database=db_name,
            user=username, password=password
        )
        
        try:
            rows = await conn.fetch("""
                SELECT 
                    query,
                    calls,
                    round((total_exec_time / calls)::numeric, 2) AS avg_time_ms,
                    round(total_exec_time::numeric, 2) AS total_time_ms,
                    round(stddev_exec_time::numeric, 2) AS stddev_ms,
                    rows,
                    round(100.0 * shared_blks_hit / 
                        NULLIF(shared_blks_hit + shared_blks_read, 0), 2) AS cache_hit_pct
                FROM pg_stat_statements
                WHERE calls > 5
                  AND (total_exec_time / calls) > $1
                ORDER BY avg_time_ms DESC
                LIMIT $2
            """, threshold_ms, limit)
            
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def get_index_suggestions(
        self, host: str, port: int, db_name: str,
        username: str, password: str
    ) -> List[Dict]:
        """Identify tables with sequential scans that might benefit from indexes."""
        
        conn = await asyncpg.connect(
            host=host, port=port, database=db_name,
            user=username, password=password
        )
        
        try:
            rows = await conn.fetch("""
                SELECT 
                    schemaname,
                    tablename,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    idx_tup_fetch,
                    n_live_tup,
                    CASE WHEN seq_scan > 0 
                         THEN round(100.0 * idx_scan / (idx_scan + seq_scan), 2)
                         ELSE 100 END AS index_usage_pct
                FROM pg_stat_user_tables
                WHERE seq_scan > 100
                  AND n_live_tup > 10000
                ORDER BY seq_tup_read DESC
                LIMIT 20
            """)
            
            suggestions = []
            for row in rows:
                d = dict(row)
                if d['index_usage_pct'] < 90:
                    d['suggestion'] = (
                        f"Table '{d['tablename']}' has {d['seq_scan']} sequential scans "
                        f"with {d['index_usage_pct']}% index usage. Consider adding indexes."
                    )
                    suggestions.append(d)
            
            return suggestions
        finally:
            await conn.close()

    async def get_db_health(
        self, host: str, port: int, db_name: str,
        username: str, password: str
    ) -> Dict:
        """Comprehensive health check."""
        
        conn = await asyncpg.connect(
            host=host, port=port, database=db_name,
            user=username, password=password
        )
        
        try:
            # Connection count
            conns = await conn.fetchrow("""
                SELECT 
                    count(*) as total,
                    count(*) FILTER (WHERE state = 'active') as active,
                    count(*) FILTER (WHERE state = 'idle') as idle,
                    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_tx,
                    max_conn.setting::int as max_connections
                FROM pg_stat_activity
                CROSS JOIN (SELECT setting FROM pg_settings WHERE name = 'max_connections') max_conn
                WHERE datname = $1
            """, db_name)
            
            # Database size
            db_size = await conn.fetchrow("""
                SELECT pg_database_size($1) as size_bytes,
                       pg_size_pretty(pg_database_size($1)) as size_pretty
            """, db_name)
            
            # Replication lag (if replica)
            rep_lag = await conn.fetchval("""
                SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp()))
            """)
            
            # Cache hit ratio
            cache = await conn.fetchrow("""
                SELECT 
                    round(100.0 * sum(blks_hit) / 
                        NULLIF(sum(blks_hit) + sum(blks_read), 0), 2) as cache_hit_ratio
                FROM pg_stat_database 
                WHERE datname = $1
            """, db_name)
            
            # Lock waits
            locks = await conn.fetchval("""
                SELECT count(*) FROM pg_locks l
                JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE NOT l.granted
            """)
            
            return {
                "connections": dict(conns),
                "storage": dict(db_size),
                "replication_lag_seconds": rep_lag,
                "cache_hit_ratio": float(cache['cache_hit_ratio'] or 0),
                "waiting_locks": locks,
                "healthy": (
                    float(cache['cache_hit_ratio'] or 0) > 95 and
                    locks < 5 and
                    (conns['total'] / conns['max_connections']) < 0.8
                )
            }
        finally:
            await conn.close()