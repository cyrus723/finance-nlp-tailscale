# Running the Finance NLP Pipeline on GitHub Actions

This guide walks you through running the Finance NLP workflow directly from
GitHub — no local setup, no server, no cost.

---

## What happens when you run it

GitHub spins up a free Ubuntu machine in the cloud, starts all four Tailscale
nodes on it (ingestion, NLP, storage, dashboard), runs the full pipeline, and
saves the results for you to download.

```
GitHub Runner (cloud VM)
┌────────────────────────────────────────────────────┐
│                                                    │
│  [ingestion :8001] ──► [nlp :8002]                │
│         │                    │                     │
│         └──────────► [storage :8003]               │
│                            ▲                       │
│                    [dashboard :8000]  ◄── Actions  │
│                                                    │
└────────────────────────────────────────────────────┘
         Results saved as downloadable artifacts
```

---

## Step-by-step

### Step 1 — Open the repository

Go to:
```
https://github.com/cyrus723/finance-nlp-tailscale
```

---

### Step 2 — Go to the Actions tab

Click the **Actions** tab in the top navigation bar of the repository.

```
< > Code   Issues   Pull requests   Actions   Projects   ...
                                    ^^^^^^^^^
                                    click here
```

---

### Step 3 — Select the workflow

In the left sidebar you will see:

```
All workflows
─────────────
Finance NLP Pipeline      ◄── click this
```

---

### Step 4 — Run the workflow

On the right side of the page, click the **"Run workflow"** dropdown button.

```
                              ┌─────────────────────┐
                              │   Run workflow  ▼   │
                              └─────────────────────┘
```

A small form appears with two inputs:

| Field | Description | Options |
|-------|-------------|---------|
| **RSS feed to fetch from** | Which financial news source to use | `yahoo_finance`, `reuters_business`, `cnbc_top`, `marketwatch`, `seeking_alpha` |
| **Number of articles to analyse** | How many articles to process (1–30) | Default: `10` |

Fill in your choices, then click the green **"Run workflow"** button at the bottom
of the form.

---

### Step 5 — Watch it run

The workflow appears in the list with an orange spinning indicator.
Click on it to watch the live log.

You will see each node start up in sequence:

```
✓ Checkout
✓ Set up Python 3.11
✓ Install dependencies
✓ Start ingestion node (port 8001)
✓ Start NLP processor node (port 8002)
✓ Start storage node (port 8003)
✓ Start dashboard node (port 8000)
✓ Wait for all nodes to be ready
⟳ Run Finance NLP pipeline        ◄── pipeline executing here
  Generate HTML report
  Write job summary
  Upload results
```

Total runtime is roughly **2 minutes**.

---

### Step 6 — View the results

When the run turns green (passed), scroll down on the run page.

#### 6a — Job Summary (inline Markdown table)

Directly on the run page you will see a results table like this:

```
## Finance NLP Pipeline Results

| Metric            | Value         |
|-------------------|---------------|
| Source            | yahoo_finance |
| Articles fetched  | 10            |
| Articles analysed | 10            |
| Elapsed           | 1.8s          |

### Sentiment Breakdown
| Label   | Count |
|---------|-------|
| Bullish | 3     |
| Bearish | 2     |
| Neutral | 5     |

### Articles
| Title                                  | Sentiment | Score   | Tickers    |
|----------------------------------------|-----------|---------|------------|
| Nvidia beats earnings expectations...  | ^ Bullish | +0.681  | NVDA, AMD  |
| Fed signals further rate hikes...      | v Bearish | -0.412  | JPM, GS    |
| ...                                    | ...       | ...     | ...        |
```

#### 6b — Downloadable HTML Report

Scroll to the bottom of the run page to the **Artifacts** section:

```
Artifacts
─────────
  finance-nlp-results-3    ◄── click to download a .zip
  (kept for 30 days)
```

Unzip and open `finance_nlp_report.html` in any browser for the full
styled dark-mode report with a colour-coded sentiment bar and article table.

#### 6c — Raw JSON

The zip also contains `pipeline_result.json` — the complete machine-readable
output with all sentiment scores and extracted entities.

---

## Changing the news source

Each run is independent. You can run the workflow multiple times with
different sources and compare results:

| Source key | Feed |
|------------|------|
| `yahoo_finance` | Yahoo Finance top stories |
| `reuters_business` | Reuters business news |
| `cnbc_top` | CNBC top stories |
| `marketwatch` | MarketWatch top stories |
| `seeking_alpha` | Seeking Alpha feed |

---

## Tailscale note

In this GitHub Actions run, all four services communicate over `localhost`
because they share the same cloud runner. This is identical to running
`python demo_local.py` on your laptop.

To run this as a **true Tailscale mesh** (each service on its own machine):

1. Provision four cloud VMs (any provider)
2. Install Tailscale on each: `curl -fsSL https://tailscale.com/install.sh | sh`
3. Authenticate each with an auth key and a tag:
   ```bash
   tailscale up --authkey=tskey-auth-xxxx --advertise-tags=tag:ingestion
   ```
4. Upload `tailscale_config/acl_policy.hujson` at
   `https://login.tailscale.com/admin/acls`
5. Start each service — they find each other by MagicDNS hostname:
   ```bash
   INGESTION_HOST=ingestion-node.tail1ab2c.ts.net python services/dashboard/main.py
   ```

See `README.md` and `docker-compose.tailscale.yml` for full deployment details.

---

## Quick reference

| What | Where |
|------|-------|
| Repository | https://github.com/cyrus723/finance-nlp-tailscale |
| Actions tab | https://github.com/cyrus723/finance-nlp-tailscale/actions |
| Workflow file | `.github/workflows/run_pipeline.yml` |
| Report scripts | `scripts/print_results.py`, `generate_report.py`, `write_summary.py` |
| Local demo | `python demo_local.py` then open http://localhost:8000 |
