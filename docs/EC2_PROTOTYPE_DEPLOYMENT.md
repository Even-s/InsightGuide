# InsightGuide EC2 Prototype Deployment

This deployment runs the complete prototype on one Ubuntu EC2 instance:

- Caddy: HTTPS, React static files, API and SSE reverse proxy
- FastAPI: application API
- Celery: document analysis and report jobs
- PostgreSQL 16 with pgvector
- Redis 7: SSE Pub/Sub and Celery broker/result backend
- MinIO: private S3-compatible object storage

It is intended for a controlled prototype, not a highly available production system.
The EC2 runtime image intentionally excludes LibreOffice and Poppler because the current
application does not invoke either tool; PDF report export is implemented with ReportLab.

Two access modes are supported:

- **Private SSM tunnel mode**: no public IP or inbound application ports; recommended for an early prototype.
- **Public HTTPS mode**: Elastic IP, two DNS records, and Caddy-managed TLS certificates.

## 1. Create the EC2 instance

Recommended public-mode starting point:

- Ubuntu 24.04 LTS, x86_64
- `t3.xlarge` (4 vCPU, 16 GiB RAM)
- 100 GiB encrypted gp3 EBS volume
- Elastic IP
- IAM role with Systems Manager access and optional write access to the backup S3 bucket

Security group inbound rules:

| Port | Source | Purpose |
| --- | --- | --- |
| 80/TCP | `0.0.0.0/0`, `::/0` | ACME challenge and HTTPS redirect |
| 443/TCP | approved client networks or public internet | Application and files |
| 443/UDP | approved client networks or public internet | HTTP/3, optional |

Do not expose ports 8002, 5432, 6379, 9000, or 9001. Prefer AWS Systems Manager Session Manager instead of public SSH.

For private SSM mode, the existing `t3.large` size is sufficient when `WEB_CONCURRENCY=1`
and `CELERY_CONCURRENCY=1`. No application inbound rules or public IP are required.

## 2. Configure access

### Private SSM tunnel mode

The EC2 instance only binds the gateway and MinIO API to loopback. Configure the environment with:

```bash
cd /opt/insightguide/deploy/ec2
cp .env.ssm.example .env
chmod 600 .env
```

After deployment, start both tunnels from the local repository and keep the terminal open:

```bash
INSTANCE_ID=i-xxxxxxxxxxxxxxxxx \
AWS_PROFILE=your-profile \
AWS_REGION=ap-northeast-1 \
  deploy/ec2/start-ssm-tunnel.sh
```

Open `http://localhost:5174`. MinIO presigned URLs use `http://localhost:9000` through
the second tunnel. Browsers treat localhost as a secure context for microphone access.

### Public HTTPS mode

Create two Route 53 `A` records pointing to the Elastic IP:

- `insightguide.example.com`
- `files.insightguide.example.com`

Caddy obtains TLS certificates only after both records resolve to the EC2 instance and ports 80/443 are reachable.

## 3. Bootstrap the host

Copy the repository to `/opt/insightguide`, then run:

```bash
cd /opt/insightguide
sudo deploy/ec2/bootstrap-ubuntu.sh
```

Sign out and back in after the script adds the current user to the `docker` group.

## 4. Configure secrets

```bash
cd /opt/insightguide/deploy/ec2
# Public HTTPS mode:
cp .env.example .env

# Or private SSM mode:
cp .env.ssm.example .env
chmod 600 .env
```

Fill in every required value. Generate secrets with URL-safe characters because the PostgreSQL and Redis passwords are embedded in connection URLs:

```bash
openssl rand -hex 32
```

The current prototype authentication is still a development stub. Until real authentication and per-user authorization are implemented, use private SSM mode or restrict HTTPS access by source IP, VPN, or another access gateway.

## 5. Deploy

```bash
cd /opt/insightguide
deploy/ec2/deploy.sh
```

The deployment script performs these operations in order:

1. Validate environment values and Docker Compose.
2. Build the backend and frontend production images.
3. Start PostgreSQL, Redis, and MinIO.
4. Create the private MinIO bucket and CORS policy.
5. Initialize a clean database from the current models, or run Alembic upgrades on an existing managed database.
6. Start FastAPI, Celery, and Caddy.
7. Verify the API health endpoint inside the container network.

Useful operations:

```bash
cd /opt/insightguide/deploy/ec2
docker compose ps
docker compose logs -f --tail=200 backend worker web
docker compose restart backend worker
```

## 6. Back up and restore

Create a local backup and optionally upload it to `AWS_BACKUP_URI`:

```bash
cd /opt/insightguide
deploy/ec2/backup.sh
```

Automate it with root cron or a systemd timer. The EC2 IAM role needs access to the configured S3 backup prefix when off-instance upload is enabled.

Restore requires an explicit confirmation value:

```bash
cd /opt/insightguide
RESTORE_CONFIRM=restore-20260715T120000Z \
  deploy/ec2/restore.sh 20260715T120000Z
```

Restore stops all application writers, restores PostgreSQL and MinIO, reapplies migrations, and restarts the services.

## 7. Prototype acceptance checks

After deployment, verify:

1. Home page and React deep links load through the selected HTTPS or SSM access mode.
2. Project creation and document upload work.
3. Celery completes document analysis after a worker restart.
4. Editor analysis progress arrives through SSE.
5. OpenAI Realtime starts from the browser and completed utterances persist.
6. An interrupted interview can resume with prior card completion state.
7. Insight memo, evidence matrix, transcript, and BRD generation work.
8. Presigned MinIO downloads use the configured public files origin or local MinIO tunnel.
9. A backup can be restored on an empty test instance.

## Known prototype limitations

- One EC2 failure takes down every runtime and data service.
- Docker volumes live on one EBS volume.
- Deployments briefly restart API and worker containers.
- FastAPI background tasks that have not moved to Celery can be lost during a restart.
- Authentication and authorization must be completed before unrestricted public access.
- `/health` is currently a liveness response, not a full PostgreSQL/Redis readiness check.
- The prototype uses the clean baseline Alembic migration. Deployment bootstrap can initialize an
  empty database and stamp the current head, but it refuses to guess the state of a populated
  database that has no `alembic_version` table.
- PDF and DOCX source-document parsing needs a separate implementation review. The EC2 image does
  not install LibreOffice or Poppler because neither executable is called by the current application.
