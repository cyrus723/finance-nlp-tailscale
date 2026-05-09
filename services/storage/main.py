"""
Storage Node — Finance NLP over Tailscale
==========================================
Role  : Persists articles and NLP analyses in SQLite; serves query endpoints.
Port  : 8003
Peers : Called by the Dashboard node to write and read data.

TAILSCALE CONCEPT — Subnet routing:
  In production this node could be replaced by a PostgreSQL server inside a
  corporate network.  Tailscale's subnet router feature lets one Tailscale node
  advertise a CIDR (e.g. 10.0.1.0/24) to the mesh.  All other nodes can then
  reach that entire subnet without installing Tailscale on each database server.
  Command: tailscale up --advertise-routes=10.0.1.0/24
"""

import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Annotated

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from _shared.auth import require_internal_key

logger = logging.getLogger(__name__)

from models import (
    init_db, insert_article, insert_analysis,
    log_run, query_recent, query_sentiment_summary, query_top_tickers,
)

app = FastAPI(
    title="Finance Storage Node",
    description="Persists and queries NLP-enriched financial articles",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    init_db()


# ── Request models ────────────────────────────────────────────────────────────

class ArticleIn(BaseModel):
    title:     Annotated[str, Field(min_length=1, max_length=1_000)]
    summary:   Optional[Annotated[str, Field(max_length=5_000)]] = None
    link:      Optional[Annotated[str, Field(max_length=2_048)]] = None
    published: Optional[Annotated[str, Field(max_length=100)]]  = None
    source:    Optional[Annotated[str, Field(max_length=100)]]  = None


class AnalysisIn(BaseModel):
    article_id: int
    nlp_result: dict


class RunLogIn(BaseModel):
    source:      Optional[Annotated[str, Field(max_length=100)]] = None
    articles_in: Annotated[int, Field(ge=0)] = 0
    analyzed:    Annotated[int, Field(ge=0)] = 0
    bullish:     Annotated[int, Field(ge=0)] = 0
    bearish:     Annotated[int, Field(ge=0)] = 0
    neutral:     Annotated[int, Field(ge=0)] = 0


# ── Write endpoints ───────────────────────────────────────────────────────────

@app.get("/", summary="Health check")
def root():
    return {"service": "storage-node", "status": "ok"}


@app.post("/articles", summary="Store a new article",
          dependencies=[Depends(require_internal_key)])
def create_article(article: ArticleIn):
    """
    Stores an article fetched by the Ingestion node.

    TAILSCALE CONCEPT — Node identity:
      Tailscale identifies each node by a WireGuard public key.  When this
      endpoint receives a request, the Dashboard node is authenticated by its
      Tailscale identity — no username/password required.
    """
    try:
        article_id = insert_article(article.model_dump())
        return {"article_id": article_id}
    except Exception:
        logger.exception("Failed to insert article")
        raise HTTPException(status_code=500, detail="Storage error")


@app.post("/analyses", summary="Store NLP analysis for an article",
          dependencies=[Depends(require_internal_key)])
def create_analysis(payload: AnalysisIn):
    """Stores the NLP result produced by the NLP Processor node."""
    try:
        analysis_id = insert_analysis(payload.article_id, payload.nlp_result)
        return {"analysis_id": analysis_id}
    except Exception:
        logger.exception("Failed to insert analysis")
        raise HTTPException(status_code=500, detail="Storage error")


@app.post("/runs", summary="Log a pipeline run summary",
          dependencies=[Depends(require_internal_key)])
def log_pipeline_run(run: RunLogIn):
    try:
        log_run(run.model_dump())
        return {"status": "logged"}
    except Exception:
        logger.exception("Failed to log run")
        raise HTTPException(status_code=500, detail="Storage error")


# ── Read endpoints ────────────────────────────────────────────────────────────

@app.get("/articles/recent", summary="Most recent analysed articles")
def recent_articles(limit: int = 20):
    """
    Returns the latest articles with their NLP results joined in.

    TAILSCALE CONCEPT — Funnel node:
      Only the Dashboard node needs read access to this endpoint. We enforce
      that in the ACL policy (see tailscale_config/acl_policy.hujson) using
      node tags, so other nodes (e.g. ingestion) cannot query stored data.
    """
    return JSONResponse(content=query_recent(limit))


@app.get("/stats/sentiment", summary="Aggregate sentiment distribution")
def sentiment_stats():
    """Global Bullish / Bearish / Neutral breakdown across all stored articles."""
    return JSONResponse(content=query_sentiment_summary())


@app.get("/stats/tickers", summary="Most mentioned tickers")
def top_tickers(limit: int = 10):
    """Ranks tickers by how often they appear across all stored analyses."""
    return JSONResponse(content=query_top_tickers(limit))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("STORAGE_PORT", 8003))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
