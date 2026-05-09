"""
NLP Processor Node — Finance NLP over Tailscale
================================================
Role  : Runs sentiment analysis and financial entity extraction.
Port  : 8002
Peers : Called by the Dashboard node; calls nothing upstream.

TAILSCALE CONCEPT — Peer-to-peer encryption:
  Traffic from the Dashboard node to this service travels over a WireGuard
  tunnel established by Tailscale.  Every packet is encrypted end-to-end with
  public-key cryptography — even if both nodes are on the same LAN.
  No SSL certificates to manage; Tailscale handles key rotation automatically.
"""

import os
import time
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from sentiment import FinanceSentimentAnalyzer
from entities import extract_as_dict

app = FastAPI(
    title="Finance NLP Processor Node",
    description="Sentiment analysis and entity extraction for financial text",
    version="1.0.0",
)

_analyzer = FinanceSentimentAnalyzer()


# ── Request / Response models ─────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    text: str
    source: Optional[str] = None
    metadata: Optional[dict] = None


class BatchAnalyzeRequest(BaseModel):
    items: list[AnalyzeRequest]


class AnalysisResult(BaseModel):
    text:      str
    sentiment: dict
    entities:  dict
    source:    Optional[str]
    processed_at: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", summary="Health check")
def root():
    """
    Health probe.  The Dashboard node calls this on startup to confirm the
    NLP node is reachable through the Tailscale mesh.
    """
    return {"service": "nlp-processor-node", "status": "ok"}


@app.post("/analyze", response_model=AnalysisResult, summary="Analyze one text")
def analyze(req: AnalyzeRequest = Body(...)):
    """
    Full NLP pipeline for a single text:
      1. Sentiment scoring (VADER + finance lexicon)
      2. Financial entity extraction (tickers, amounts, percentages, dates)

    TAILSCALE CONCEPT — Access Control Lists (ACLs):
      Only nodes tagged `tag:nlp-consumer` in the ACL policy are allowed to
      POST to this endpoint.  The Tailscale control plane enforces this — no
      application-level auth needed.  See tailscale_config/acl_policy.hujson.
    """
    sentiment = _analyzer.analyze(req.text)
    entities  = extract_as_dict(req.text)

    return {
        "text":         req.text,
        "sentiment":    sentiment,
        "entities":     entities,
        "source":       req.source,
        "processed_at": time.time(),
    }


@app.post("/analyze/batch", summary="Analyze a list of texts")
def analyze_batch(req: BatchAnalyzeRequest = Body(...)):
    """
    Processes multiple articles in one round-trip — reduces latency over the
    Tailscale mesh compared to N individual requests.

    TAILSCALE CONCEPT — WireGuard performance:
      Tailscale's WireGuard tunnels are extremely low-overhead (~4% CPU) and
      add only ~0.1 ms of latency on the same continent.  Batching is still
      good practice but the mesh is fast enough that individual calls work too.
    """
    results = []
    for item in req.items:
        sentiment = _analyzer.analyze(item.text)
        entities  = extract_as_dict(item.text)
        results.append({
            "text":         item.text,
            "sentiment":    sentiment,
            "entities":     entities,
            "source":       item.source,
            "processed_at": time.time(),
        })
    return JSONResponse(content={"results": results, "count": len(results)})


@app.post("/sentiment", summary="Sentiment only (faster)")
def sentiment_only(req: AnalyzeRequest = Body(...)):
    """Returns only the sentiment scores — skips entity extraction for speed."""
    return _analyzer.analyze(req.text)


@app.post("/entities", summary="Entity extraction only")
def entities_only(req: AnalyzeRequest = Body(...)):
    """Returns only extracted financial entities — skips sentiment scoring."""
    return extract_as_dict(req.text)


@app.get("/lexicon/finance", summary="View finance lexicon boosters")
def get_finance_lexicon():
    """Exposes the finance-specific sentiment boosters for transparency."""
    from sentiment import FINANCE_LEXICON
    return {"lexicon": FINANCE_LEXICON, "size": len(FINANCE_LEXICON)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("NLP_PORT", 8002))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
