# Finance NLP — Powered by Tailscale

A **distributed Finance NLP pipeline** that demonstrates the core benefits of
Tailscale by connecting four independent microservices over a secure mesh
network.  Every call between services travels through a WireGuard-encrypted
tunnel managed by Tailscale — no port-forwarding, no static IPs, no VPN
gateway.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Tailscale Mesh Network                       │
│                                                                 │
│  ┌──────────────┐   MagicDNS    ┌──────────────┐               │
│  │  Ingestion   │◄──────────────│  Dashboard   │               │
│  │  Node :8001  │               │  Node :8000  │◄── Browser    │
│  │  (RSS/Yahoo) │               │ (Orchestrator│               │
│  └──────────────┘               │  + Web UI)   │               │
│                                 └──────┬───────┘               │
│  ┌──────────────┐                      │                        │
│  │  NLP         │◄─────────────────────┤                        │
│  │  Node :8002  │               MagicDNS                        │
│  │  (VADER NLP) │                      │                        │
│  └──────────────┘               ┌──────▼───────┐               │
│                                 │  Storage     │               │
│                                 │  Node :8003  │               │
│                                 │  (SQLite)    │               │
│                                 └──────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

---

## What does it do?

| Step | Node | What happens |
|------|------|-------------|
| 1 | **Ingestion** | Fetches live financial news from Yahoo Finance, Reuters, CNBC, MarketWatch via RSS |
| 2 | **NLP Processor** | Scores sentiment (Bullish / Bearish / Neutral) using VADER + a finance lexicon; extracts tickers, companies, $ amounts, % changes |
| 3 | **Storage** | Persists every article and its NLP result in SQLite; serves aggregate stats |
| 4 | **Dashboard** | Orchestrates the pipeline and renders results in a live web UI |

---

## Tailscale Concepts Explained

### 1. Mesh Network (vs hub-and-spoke VPN)

```
Traditional VPN          Tailscale Mesh
─────────────            ──────────────
  A → Gateway → B        A ↔ B  (direct)
  C → Gateway → D        C ↔ D  (direct)
  (all traffic bottlenecks at gateway)   (each pair is a direct WireGuard tunnel)
```

Tailscale builds a **full mesh**: every node talks directly to every other
node, peer-to-peer.  Latency is minimal (no gateway hop).  There is still a
coordination server (Tailscale's control plane) but it only handles
authentication and key exchange — data never flows through it.

### 2. WireGuard Encryption

Each tunnel between two nodes uses **WireGuard**, a modern VPN protocol.
Key properties:
- **Noise Protocol handshake** — mutual authentication without certificates
- **ChaCha20-Poly1305** encryption — fast on CPUs without AES hardware
- **Automatic key rotation** — keys are refreshed every 3 minutes
- You manage **nothing** — Tailscale automates all of this.

### 3. MagicDNS — No more IP addresses

When MagicDNS is enabled every node gets a stable DNS name:

```
ingestion-node.tail1ab2c.ts.net  →  100.64.0.5
nlp-node.tail1ab2c.ts.net        →  100.64.0.6
storage-node.tail1ab2c.ts.net    →  100.64.0.7
dashboard-node.tail1ab2c.ts.net  →  100.64.0.8
```

In this project the Dashboard calls peers like:

```python
NLP_URL = "http://nlp-node.tail1ab2c.ts.net:8002"
```

Restart the NLP service on a different cloud VM?  The IP changes, the name
doesn't.  Zero config changes needed.

### 4. ACL Policy — Zero-trust access control

Tailscale ACLs define exactly which node can talk to which other node on which
port.  Open [`tailscale_config/acl_policy.hujson`](tailscale_config/acl_policy.hujson).

Key rules in our policy:
- `tag:dashboard` → `tag:ingestion:8001` — Dashboard can fetch news
- `tag:dashboard` → `tag:nlp:8002` — Dashboard can run NLP
- `tag:dashboard` → `tag:storage:8003` — Dashboard can read/write data
- Ingestion **cannot** call Storage directly (no rule = denied)
- Admins can SSH into any node via **Tailscale SSH** (no key distribution)

### 5. Tailscale SSH — Identity-based remote access

```bash
# Traditional SSH (requires distributing public keys):
ssh -i ~/.ssh/id_ed25519 ubuntu@10.0.0.5

# Tailscale SSH (identity from your Google/GitHub login):
tailscale ssh ubuntu@nlp-node
```

No key rotation, no `authorized_keys` file management, revoke access instantly
by removing a device from the admin console.

### 6. Subnet Router — Bridge existing networks

If your database lives on `10.0.1.0/24` inside a corporate network, one
Tailscale node can advertise that subnet to the whole mesh:

```bash
tailscale up --advertise-routes=10.0.1.0/24
```

Every other node can now reach `10.0.1.5` (your PostgreSQL server) without
installing Tailscale on the DB host itself.

### 7. Funnel — Expose one service to the internet

The Dashboard node can be made publicly accessible without opening firewall
ports:

```bash
tailscale funnel 8000
# → https://dashboard-node.tail1ab2c.ts.net  (publicly reachable)
```

All other nodes stay private.  Tailscale handles TLS termination.

### 8. Auth Keys — Headless / CI/CD deployment

To add a new node without a browser login (e.g. a cloud VM):

```bash
# Generate at https://login.tailscale.com/admin/settings/keys
tailscale up --authkey=tskey-auth-xxxx --advertise-tags=tag:nlp
```

One key can be reusable and tag-restricted so automated deployments can only
join with specific roles.

---

## Quick Start (local, no Tailscale required)

### Option A — Single script (fastest)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run all four services + a demo pipeline
python demo_local.py
```

Open `http://localhost:8000` in your browser.

### Option B — Docker Compose

```bash
docker compose up --build
# → http://localhost:8000
```

### Option C — Tailscale deployment (4 machines)

```
1. Install Tailscale on each machine:
   https://tailscale.com/download

2. Authenticate each machine:
   tailscale up --authkey=tskey-auth-xxxx --advertise-tags=tag:ingestion
   tailscale up --authkey=tskey-auth-xxxx --advertise-tags=tag:nlp
   tailscale up --authkey=tskey-auth-xxxx --advertise-tags=tag:storage
   tailscale up --authkey=tskey-auth-xxxx --advertise-tags=tag:dashboard

3. Upload the ACL policy:
   https://login.tailscale.com/admin/acls
   (paste tailscale_config/acl_policy.hujson)

4. On each machine, start its service:
   ingestion-node$ python services/ingestion/main.py
   nlp-node$       python services/nlp_processor/main.py
   storage-node$   python services/storage/main.py
   dashboard-node$ INGESTION_HOST=ingestion-node NLP_HOST=nlp-node \
                   STORAGE_HOST=storage-node python services/dashboard/main.py

5. Open http://dashboard-node.tail1ab2c.ts.net:8000
```

Or use the Tailscale Docker Compose:

```bash
cp .env.example .env
# edit .env → set TAILSCALE_AUTH_KEY
docker compose -f docker-compose.tailscale.yml up --build
```

---

## Project Structure

```
tailscale2/
├── README.md
├── requirements.txt
├── .env.example
├── demo_local.py                        ← single-machine demo
├── docker-compose.yml                   ← local Docker (no Tailscale)
├── docker-compose.tailscale.yml         ← production Docker (with Tailscale)
├── tailscale_config/
│   └── acl_policy.hujson               ← ACL policy to upload to admin console
└── services/
    ├── ingestion/
    │   └── main.py                     ← RSS + Yahoo Finance fetcher (port 8001)
    ├── nlp_processor/
    │   ├── main.py                     ← NLP API (port 8002)
    │   ├── sentiment.py                ← VADER + finance lexicon
    │   └── entities.py                 ← ticker / amount / date extraction
    ├── storage/
    │   ├── main.py                     ← SQLite REST API (port 8003)
    │   └── models.py                   ← DB helpers
    └── dashboard/
        ├── main.py                     ← Orchestrator (port 8000)
        └── templates/index.html        ← Web dashboard
```

---

## Finance NLP Capabilities

### Sentiment Analysis
Uses [VADER](https://github.com/cjhutto/vaderSentiment) extended with a
finance-specific lexicon:

| Word / phrase | Score |
|---|---|
| "beat estimates" | +3.5 (strongly bullish) |
| "record high" | +3.5 |
| "bankruptcy" | -4.0 (strongly bearish) |
| "downgrade" | -3.0 |
| "bullish" | +3.5 |

Output:
```json
{
  "compound": 0.72,
  "positive": 0.41,
  "negative": 0.08,
  "neutral":  0.51,
  "label":    "Bullish"
}
```

### Entity Extraction
Extracts from raw text using regex + a 50-company name→ticker map:

| Entity type | Example |
|---|---|
| Tickers | AAPL, NVDA, TSLA |
| Companies | Apple, Nvidia, Tesla |
| Monetary amounts | $2.5B, $340M |
| Percentages | +12.4%, -3.1% |
| Dates | Q2 2025, May 2025 |

---

## API Reference

| Service | Endpoint | Description |
|---------|----------|-------------|
| Ingestion :8001 | `GET /news?source=yahoo_finance&limit=10` | Fetch latest news |
| Ingestion :8001 | `GET /news/all` | Aggregate all feeds |
| Ingestion :8001 | `GET /stock/{ticker}` | Market snapshot |
| NLP :8002 | `POST /analyze` | Full NLP for one text |
| NLP :8002 | `POST /analyze/batch` | Batch NLP |
| NLP :8002 | `POST /sentiment` | Sentiment only |
| NLP :8002 | `POST /entities` | Entities only |
| Storage :8003 | `POST /articles` | Store article |
| Storage :8003 | `GET /articles/recent` | Latest articles |
| Storage :8003 | `GET /stats/sentiment` | Aggregate distribution |
| Storage :8003 | `GET /stats/tickers` | Top mentioned tickers |
| Dashboard :8000 | `GET /` | Web UI |
| Dashboard :8000 | `GET /api/run` | Trigger pipeline |
| Dashboard :8000 | `GET /api/health` | Node health check |
| Dashboard :8000 | `GET /api/stats` | Aggregate stats |

Auto-generated Swagger docs available at `http://<node>:<port>/docs`.

---

## Why Tailscale for this use case?

| Challenge | Without Tailscale | With Tailscale |
|-----------|-------------------|----------------|
| Service discovery | Hard-code IPs or run internal DNS | MagicDNS — stable hostnames automatically |
| Encryption in transit | Set up TLS certificates per service | WireGuard encryption — automatic, zero-config |
| Access control | Firewall rules per VM, per port | ACL policy in one file, enforced globally |
| Adding a new node | Update firewall rules, VPN config | `tailscale up` — done in 30 seconds |
| Remote access (SSH) | Distribute SSH keys, manage bastion | `tailscale ssh node-name` |
| Multi-cloud | Complex peering / VPN tunnels | Tailscale works across any network transparently |
