"""
Dashboard Node — Finance NLP over Tailscale
============================================
Role  : Orchestrates the pipeline; serves the web UI.
Port  : 8000
Peers : Calls Ingestion (8001), NLP Processor (8002), Storage (8003).

This is the "brain" of the system.  It discovers the other nodes by their
Tailscale MagicDNS hostnames, runs the end-to-end pipeline, and renders
results in a browser.

TAILSCALE CONCEPT — MagicDNS hostnames:
  Instead of hard-coding IPs like 10.0.0.5:8002, each node is reachable as:
    http://ingestion-node.tail1ab2c.ts.net:8001
    http://nlp-node.tail1ab2c.ts.net:8002
    http://storage-node.tail1ab2c.ts.net:8003
  Change the machine, the IP changes — the hostname never does.
"""

import os
import time
import httpx
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

# ── Node addresses (override with env vars / Tailscale hostnames) ─────────────
INGESTION_URL = (
    f"http://{os.getenv('INGESTION_HOST', 'localhost')}:"
    f"{os.getenv('INGESTION_PORT', '8001')}"
)
NLP_URL = (
    f"http://{os.getenv('NLP_HOST', 'localhost')}:"
    f"{os.getenv('NLP_PORT', '8002')}"
)
STORAGE_URL = (
    f"http://{os.getenv('STORAGE_HOST', 'localhost')}:"
    f"{os.getenv('STORAGE_PORT', '8003')}"
)

TIMEOUT = httpx.Timeout(30.0)

app = FastAPI(
    title="Finance NLP Dashboard",
    description="Orchestrator + web UI for the Tailscale Finance NLP pipeline",
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _check_node(client: httpx.AsyncClient, name: str, url: str) -> dict:
    try:
        r = await client.get(f"{url}/", timeout=5.0)
        return {"node": name, "url": url, "status": "online", "latency_ms": round(r.elapsed.total_seconds() * 1000, 1)}
    except Exception as exc:
        return {"node": name, "url": url, "status": "offline", "error": str(exc)}


async def _run_pipeline(source: str, limit: int) -> dict:
    """
    End-to-end pipeline:
      1. Fetch news from Ingestion node
      2. Send each article to NLP Processor node
      3. Persist results to Storage node
      4. Return aggregated results
    """
    pipeline_start = time.time()
    results = []
    errors  = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:

        # ── Step 1: Ingest ────────────────────────────────────────────────────
        try:
            r = await client.get(f"{INGESTION_URL}/news",
                                 params={"source": source, "limit": limit})
            r.raise_for_status()
            articles = r.json()
        except Exception as exc:
            return {"error": f"Ingestion node unreachable: {exc}", "results": []}

        # ── Step 2: NLP batch ─────────────────────────────────────────────────
        batch_payload = {
            "items": [
                {"text": f"{a['title']} {a.get('summary', '')}",
                 "source": a.get("source")}
                for a in articles
            ]
        }
        try:
            r = await client.post(f"{NLP_URL}/analyze/batch", json=batch_payload)
            r.raise_for_status()
            nlp_results = r.json()["results"]
        except Exception as exc:
            errors.append(f"NLP node: {exc}")
            nlp_results = [None] * len(articles)

        # ── Step 3: Store + assemble ──────────────────────────────────────────
        counts = {"Bullish": 0, "Bearish": 0, "Neutral": 0}

        for article, nlp in zip(articles, nlp_results):
            try:
                r = await client.post(f"{STORAGE_URL}/articles", json=article)
                article_id = r.json().get("article_id")
                if nlp and article_id:
                    await client.post(f"{STORAGE_URL}/analyses",
                                      json={"article_id": article_id, "nlp_result": nlp})
            except Exception as exc:
                errors.append(f"Storage: {exc}")

            if nlp:
                label = nlp.get("sentiment", {}).get("label", "Neutral")
                counts[label] = counts.get(label, 0) + 1
                results.append({
                    "title":     article["title"],
                    "link":      article.get("link", ""),
                    "source":    article.get("source", source),
                    "published": article.get("published", ""),
                    "sentiment": nlp.get("sentiment", {}),
                    "entities":  nlp.get("entities", {}),
                })

        # Log run summary
        try:
            await client.post(f"{STORAGE_URL}/runs", json={
                "source":      source,
                "articles_in": len(articles),
                "analyzed":    len(results),
                **counts,
            })
        except Exception:
            pass

    elapsed = round(time.time() - pipeline_start, 2)
    return {
        "results":      results,
        "errors":       errors,
        "counts":       counts,
        "articles_in":  len(articles),
        "analyzed":     len(results),
        "elapsed_sec":  elapsed,
        "source":       source,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, summary="Main dashboard")
async def dashboard(request: Request):
    """Renders the Finance NLP web dashboard."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/health", summary="Check all node health")
async def health_check():
    """
    Probes each Tailscale node and reports latency.

    TAILSCALE CONCEPT — Mesh topology:
      In a traditional hub-and-spoke VPN, all traffic passes through a central
      gateway.  Tailscale uses a full mesh: each node talks directly to every
      other node, peer-to-peer.  That means the dashboard-to-NLP latency is
      NOT double-counted through a gateway — it's a direct encrypted link.
    """
    async with httpx.AsyncClient() as client:
        checks = await asyncio.gather(
            _check_node(client, "ingestion-node", INGESTION_URL),
            _check_node(client, "nlp-node",       NLP_URL),
            _check_node(client, "storage-node",   STORAGE_URL),
        )
    return JSONResponse(content={"nodes": list(checks)})


@app.get("/api/run", summary="Run the full pipeline")
async def run_pipeline(
    source: str = Query("yahoo_finance", description="RSS feed key"),
    limit:  int = Query(10, ge=1, le=30),
):
    """
    Triggers the end-to-end Finance NLP pipeline:
      Ingestion → NLP Processor → Storage → Response

    TAILSCALE CONCEPT — Funnel (optional public exposure):
      The dashboard node can be exposed to the public internet via
      `tailscale funnel 8000` — a secure HTTPS reverse-proxy managed by
      Tailscale.  All other nodes stay private inside the mesh.
    """
    data = await _run_pipeline(source, limit)
    return JSONResponse(content=data)


@app.get("/api/recent", summary="Recent articles from storage")
async def recent(limit: int = Query(20)):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{STORAGE_URL}/articles/recent",
                                 params={"limit": limit})
            return JSONResponse(content=r.json())
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=503)


@app.get("/api/stats", summary="Aggregate sentiment stats")
async def stats():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            sentiment = (await client.get(f"{STORAGE_URL}/stats/sentiment")).json()
            tickers   = (await client.get(f"{STORAGE_URL}/stats/tickers")).json()
            return JSONResponse(content={"sentiment": sentiment, "top_tickers": tickers})
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=503)


@app.get("/api/nodes", summary="Show configured node addresses")
def node_addresses():
    """
    Returns the URLs used to reach peer nodes — useful for understanding how
    MagicDNS hostnames replace IP addresses in a Tailscale deployment.
    """
    return {
        "ingestion_url": INGESTION_URL,
        "nlp_url":       NLP_URL,
        "storage_url":   STORAGE_URL,
        "tip": (
            "In production, replace localhost with Tailscale MagicDNS names "
            "like ingestion-node.tail1ab2c.ts.net"
        ),
    }


# asyncio needed for gather above
import asyncio


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DASHBOARD_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
