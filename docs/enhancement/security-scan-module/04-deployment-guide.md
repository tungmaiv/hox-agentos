# Security Scan Module - Deployment Guide

> **Document Type:** Deployment Guide  
> **Status:** Draft  
> **Audience:** DevOps Engineers, System Administrators  
> **Last Updated:** 2026-03-11

---

## 1. Prerequisites

### 1.1 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB SSD |
| Network | 100 Mbps | 1 Gbps |

### 1.2 Software Requirements

- Docker 24.0+ with Docker Compose v2
- PostgreSQL 16+ (shared with AgentOS)
- Access to OSV database (for vulnerability data)

### 1.3 Access Requirements

- Docker Hub or private registry access
- Write access to AgentOS repository
- Database admin access (for migrations)
- Kubernetes access (if deploying to K8s)

---

## 2. Pre-Deployment Checklist

- [ ] PostgreSQL 16+ running and accessible
- [ ] AgentOS backend code updated with security scan client
- [ ] Docker and Docker Compose installed
- [ ] Environment variables configured
- [ ] SSL certificates ready (for production)
- [ ] Monitoring stack ready (Prometheus/Grafana)
- [ ] Backup strategy in place

---

## 3. Deployment Options

### Option A: Docker Compose (Recommended for MVP)

Best for: Development, testing, and small deployments (<100 users)

### Option B: Kubernetes (Production)

Best for: Production, high availability, auto-scaling

---

## 4. Docker Compose Deployment

### 4.1 Step 1: Build Scanner Image

```bash
# Navigate to project root
cd /path/to/blitz-agentos

# Build security scanner image
docker compose build security-scanner

# Verify build
docker images | grep security-scanner
```

### 4.2 Step 2: Database Setup

```bash
# Run database migrations
docker compose run --rm security-scanner alembic upgrade head

# Verify tables created
docker compose exec postgres psql -U blitz -d blitz -c "\dt secscan_*"
```

Expected output:
```
           List of relations
 Schema |       Name        | Type  | Owner 
--------+-------------------+-------+-------
 public | secscan_policies  | table | blitz
 public | secscan_results   | table | blitz
 public | secscan_vulnerabilities | table | blitz
```

### 4.3 Step 3: Start Service

```bash
# Start security scanner
docker compose up -d security-scanner

# Verify service is running
docker compose ps security-scanner

# Check logs
docker compose logs -f security-scanner
```

### 4.4 Step 4: Health Verification

```bash
# Test health endpoint
curl http://localhost:8003/health

# Expected response:
# {"status": "healthy", "version": "1.0.0"}

# Test readiness
curl http://localhost:8003/ready

# Expected response:
# {"status": "ready", "checks": {"database": "ok", "vuln_db": "ok"}}
```

### 4.5 Step 5: Integration Test

```bash
# From backend container
docker compose exec backend python -c "
from mcp.security_scan_client import SecurityScanClient
import asyncio

async def test():
    client = SecurityScanClient('http://security-scanner:8003')
    result = await client.scan_dependencies(
        requirements_txt='requests==2.30.0'
    )
    print(f'Status: {result[\"status\"]}')

asyncio.run(test())
"
```

---

## 5. Kubernetes Deployment

### 5.1 Namespace Setup

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: blitz-security
  labels:
    app: security-scanner
    version: v1
```

### 5.2 ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: security-scanner-config
  namespace: blitz-security
data:
  LOG_LEVEL: "info"
  SCAN_TIMEOUT: "300"
  MAX_SCAN_CONCURRENCY: "5"
  VULN_DB_UPDATE_INTERVAL: "86400"
  POLICY_UPDATE_INTERVAL: "3600"
  RESULT_RETENTION_DAYS: "90"
```

### 5.3 Secret

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: security-scanner-secrets
  namespace: blitz-security
type: Opaque
stringData:
  DATABASE_URL: "postgresql://blitz:password@postgres:5432/blitz"
```

### 5.4 Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: security-scanner
  namespace: blitz-security
  labels:
    app: security-scanner
spec:
  replicas: 2
  selector:
    matchLabels:
      app: security-scanner
  template:
    metadata:
      labels:
        app: security-scanner
    spec:
      containers:
      - name: security-scanner
        image: blitz/security-scanner:v1.0.0
        ports:
        - containerPort: 8003
          name: http
        envFrom:
        - configMapRef:
            name: security-scanner-config
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: security-scanner-secrets
              key: DATABASE_URL
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8003
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8003
          initialDelaySeconds: 5
          periodSeconds: 10
        volumeMounts:
        - name: policies
          mountPath: /app/policies
          readOnly: true
      volumes:
      - name: policies
        configMap:
          name: security-policies
```

### 5.5 Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: security-scanner
  namespace: blitz-security
spec:
  selector:
    app: security-scanner
  ports:
  - port: 8003
    targetPort: 8003
    name: http
  type: ClusterIP
```

### 5.6 Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: security-scanner
  namespace: blitz-security
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: security-scanner
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 5.7 Apply Configuration

```bash
# Apply all resources
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

# Verify deployment
kubectl get pods -n blitz-security
kubectl get svc -n blitz-security
```

---

## 6. Environment Configuration

### 6.1 Required Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `LOG_LEVEL` | No | `info` | Logging level |
| `SCAN_TIMEOUT` | No | `300` | Max scan time (seconds) |
| `MAX_SCAN_CONCURRENCY` | No | `5` | Concurrent scans allowed |
| `VULN_DB_UPDATE_INTERVAL` | No | `86400` | Seconds between CVE updates |
| `POLICY_UPDATE_INTERVAL` | No | `3600` | Seconds between policy reloads |
| `RESULT_RETENTION_DAYS` | No | `90` | Days to keep scan results |

### 6.2 Production Configuration

```bash
# .env.production
DATABASE_URL=postgresql://blitz:${POSTGRES_PASSWORD}@postgres.blitz.svc.cluster.local:5432/blitz
LOG_LEVEL=warning
SCAN_TIMEOUT=600
MAX_SCAN_CONCURRENCY=10
VULN_DB_UPDATE_INTERVAL=43200
POLICY_UPDATE_INTERVAL=1800
RESULT_RETENTION_DAYS=180
```

### 6.3 Development Configuration

```bash
# .env.development
DATABASE_URL=postgresql://blitz:blitz@localhost:5432/blitz
LOG_LEVEL=debug
SCAN_TIMEOUT=60
MAX_SCAN_CONCURRENCY=2
VULN_DB_UPDATE_INTERVAL=3600
POLICY_UPDATE_INTERVAL=60
RESULT_RETENTION_DAYS=7
```

---

## 7. Security Configuration

### 7.1 Network Security

**Docker Compose:**
```yaml
# Only expose to internal network
security-scanner:
  networks:
    - blitz-net
  # No ports exposed to host
  # Only accessible within blitz-net
```

**Kubernetes:**
```yaml
# Use NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: security-scanner-network-policy
  namespace: blitz-security
spec:
  podSelector:
    matchLabels:
      app: security-scanner
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: backend
    ports:
    - protocol: TCP
      port: 8003
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
```

### 7.2 Resource Limits

```yaml
# Prevent resource exhaustion
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "1000m"
```

### 7.3 Pod Security

```yaml
# Run as non-root
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  capabilities:
    drop:
    - ALL
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  seccompProfile:
    type: RuntimeDefault
```

---

## 8. Monitoring Setup

### 8.1 Prometheus Metrics

The scanner exposes metrics at `/metrics`:

```yaml
# Prometheus scrape config
scrape_configs:
  - job_name: 'security-scanner'
    static_configs:
      - targets: ['security-scanner:8003']
    metrics_path: /metrics
    scrape_interval: 30s
```

### 8.2 Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `security_scans_total` | Counter | Total scans by type |
| `security_scan_duration_seconds` | Histogram | Scan duration |
| `security_vulnerabilities_found` | Counter | Vulns by severity |
| `security_scan_errors` | Counter | Failed scans |
| `security_policy_violations` | Counter | Policy violations |

### 8.3 Grafana Dashboard

Import dashboard JSON (provided separately) or create panels:

```json
{
  "dashboard": {
    "title": "Security Scanner",
    "panels": [
      {
        "title": "Scan Rate",
        "targets": [
          {
            "expr": "rate(security_scans_total[5m])"
          }
        ]
      },
      {
        "title": "Vulnerabilities Found",
        "targets": [
          {
            "expr": "security_vulnerabilities_found"
          }
        ]
      }
    ]
  }
}
```

---

## 9. Backup and Recovery

### 9.1 Database Backup

```bash
# Backup scan results
docker compose exec postgres pg_dump \
  -U blitz \
  -t secscan_results \
  -t secscan_policies \
  -t secscan_vulnerabilities \
  blitz > security_scanner_backup.sql

# Or using Kubernetes
kubectl exec -n blitz-security postgres-pod -- \
  pg_dump -U blitz -t secscan_* blitz > backup.sql
```

### 9.2 Automated Backups

```yaml
# k8s/cronjob-backup.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: security-scanner-backup
  namespace: blitz-security
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:16-alpine
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -h postgres -U blitz -t secscan_* blitz |
              gzip > /backup/security-scanner-$(date +%Y%m%d).sql.gz
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
            volumeMounts:
            - name: backup
              mountPath: /backup
          volumes:
          - name: backup
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

### 9.3 Recovery Procedure

```bash
# Restore from backup
docker compose exec -T postgres psql -U blitz blitz < security_scanner_backup.sql

# Verify restoration
docker compose exec postgres psql -U blitz -c "SELECT COUNT(*) FROM secscan_results;"
```

---

## 10. Maintenance Procedures

### 10.1 Updates

**Docker Compose:**
```bash
# Pull latest image
docker compose pull security-scanner

# Restart with new image
docker compose up -d security-scanner

# Verify
docker compose ps security-scanner
```

**Kubernetes:**
```bash
# Rolling update
kubectl set image deployment/security-scanner \
  security-scanner=blitz/security-scanner:v1.1.0 \
  -n blitz-security

# Monitor rollout
kubectl rollout status deployment/security-scanner -n blitz-security
```

### 10.2 Log Rotation

```yaml
# Docker Compose
security-scanner:
  logging:
    driver: "json-file"
    options:
      max-size: "100m"
      max-file: "5"
```

### 10.3 Database Cleanup

```bash
# Run retention cleanup
docker compose exec security-scanner python -c "
from database.repository import ScanRepository
import asyncio
from core.db import async_session

async def cleanup():
    async with async_session() as session:
        repo = ScanRepository(session)
        deleted = await repo.delete_old_scans(retention_days=90)
        print(f'Deleted {deleted} old scan records')

asyncio.run(cleanup())
"
```

---

## 11. Troubleshooting

### 11.1 Service Won't Start

```bash
# Check logs
docker compose logs security-scanner

# Common issues:
# 1. Database connection
# 2. Missing environment variables
# 3. Port conflict

# Debug mode
docker compose exec security-scanner python -c "
import os
print('DATABASE_URL:', os.getenv('DATABASE_URL'))
"
```

### 11.2 Database Connection Issues

```bash
# Test connection
docker compose exec security-scanner python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test():
    engine = create_async_engine('postgresql+asyncpg://blitz:blitz@postgres/blitz')
    async with engine.connect() as conn:
        result = await conn.execute('SELECT 1')
        print(result.scalar())

asyncio.run(test())
"
```

### 11.3 High Memory Usage

```bash
# Check memory usage
docker stats security-scanner

# Reduce concurrency
# Edit docker-compose.yml:
environment:
  - MAX_SCAN_CONCURRENCY=2

# Restart
docker compose up -d security-scanner
```

### 11.4 Scanner Timeouts

```bash
# Increase timeout
# Edit docker-compose.yml:
environment:
  - SCAN_TIMEOUT=600

# Check for slow queries
docker compose exec postgres psql -U blitz -c "
SELECT query, query_start 
FROM pg_stat_activity 
WHERE state = 'active' 
AND query_start < NOW() - INTERVAL '5 minutes';
"
```

---

## 12. Rollback Procedure

### 12.1 Quick Rollback

```bash
# Stop service
docker compose stop security-scanner

# Remove service from compose
# Edit docker-compose.yml and comment out security-scanner

# Restart AgentOS without scanner
docker compose up -d

# Verify AgentOS still works
curl http://localhost:8000/health
```

### 12.2 Database Rollback

```bash
# Downgrade migrations
docker compose run --rm security-scanner alembic downgrade -1

# Or drop tables manually
docker compose exec postgres psql -U blitz -c "
DROP TABLE IF EXISTS secscan_results;
DROP TABLE IF EXISTS secscan_policies;
DROP TABLE IF EXISTS secscan_vulnerabilities;
"
```

---

## 13. Production Checklist

Before deploying to production:

- [ ] SSL/TLS certificates configured
- [ ] Database backups automated
- [ ] Monitoring and alerting active
- [ ] Resource limits configured
- [ ] Network policies applied
- [ ] Pod security context set
- [ ] Log aggregation configured
- [ ] Health checks passing
- [ ] Load testing completed
- [ ] Runbook documented
- [ ] On-call rotation notified

---

*Document Version: 1.0*  
*Last Updated: 2026-03-11*
