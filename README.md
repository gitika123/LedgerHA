# LedgerHA

Fault-tolerant **order ledger** on **Amazon RDS Multi-AZ PostgreSQL** with a FastAPI service that reads/writes real SQL access patterns. Built to practice AWS Data Services interview themes: durable SQL storage, Multi-AZ high availability, indexed queries, and failover behavior.

## Why this exists

A single-AZ database is a single point of failure. LedgerHA puts the primary store on **RDS Multi-AZ** (synchronous standby in a second AZ) and runs an application against concrete SQL paths an interviewer can whiteboard:

| Access pattern | SQL shape |
|---|---|
| Create order | `INSERT` into `orders` |
| Get by id | `SELECT … WHERE id = $1` (PK) |
| List by status | `SELECT … WHERE status = $1 ORDER BY updated_at` (secondary index) |
| List recent for customer | `SELECT … WHERE customer_id = $1 ORDER BY created_at DESC` (index) |

## Architecture

```text
Client / curl
    │
    ▼
FastAPI (Python)  ── SQLAlchemy / psycopg ──►  Amazon RDS PostgreSQL (Multi-AZ)
                                                   │
                                                   ├─ Writer (AZ-a)
                                                   └─ Standby (AZ-b)  ← auto failover target
Infra (Terraform): VPC · private subnets · DB subnet group · SG · Secrets Manager
```

## Repo layout

```text
LedgerHA/
├── README.md
├── infra/                 # Terraform: VPC + Multi-AZ RDS PostgreSQL
├── app/                   # FastAPI ledger service
├── scripts/               # schema bootstrap + failover checklist
└── docs/failover.md       # how to exercise Multi-AZ failover safely
```

## Quick start (local Postgres first)

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ledgerha
python -m app.bootstrap_schema
uvicorn app.main:app --reload --port 8080
```

```bash
curl -X POST localhost:8080/orders -H 'content-type: application/json' \
  -d '{"customer_id":"c1","sku":"WIDGET","amount_cents":1999}'
curl 'localhost:8080/orders?status=OPEN'
```

## Deploy RDS Multi-AZ (AWS)

```bash
cd infra
terraform init
terraform apply   # set tfvars: project name, engine postgres, instance class
# copy DATABASE_URL from Secrets Manager / output
```

Then point `DATABASE_URL` at the RDS writer endpoint and rerun the app (preferably from a bastion / private subnet / SSM host).

