"""
Ingestion Node — Finance NLP over Tailscale
============================================
Role  : Fetches financial news from public RSS feeds and Yahoo Finance.
Port  : 8001
Peers : Called by the Dashboard node.

TAILSCALE CONCEPT — Why this node exists as a separate service:
  In a real deployment each node runs on its own machine (cloud VM, on-prem
  server, Raspberry Pi, etc.).  Tailscale creates a private mesh network so
  every node can reach every other node using a stable MagicDNS hostname like
  "ingestion-node.tail1ab2c.ts.net", regardless of which ISP or cloud provider
  hosts them.  No firewall rules, no VPN gateway, no port-forwarding needed.
"""

import os
import re
import time
import logging
import feedparser
import yfinance as yf
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Finance Ingestion Node",
    description="Fetches financial news and market snapshots over Tailscale",
    version="1.0.0",
)

class NewsSource(str, Enum):
    yahoo_finance    = "yahoo_finance"
    reuters_business = "reuters_business"
    cnbc_top         = "cnbc_top"
    seeking_alpha    = "seeking_alpha"
    marketwatch      = "marketwatch"

# ── RSS feed catalogue (public, no API key required) ──────────────────────────
RSS_FEEDS = {
    NewsSource.yahoo_finance:    "https://finance.yahoo.com/rss/topstories",
    NewsSource.reuters_business: "https://feeds.reuters.com/reuters/businessNews",
    NewsSource.cnbc_top:         "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    NewsSource.seeking_alpha:    "https://seekingalpha.com/feed.xml",
    NewsSource.marketwatch:      "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}

TICKER_PATTERN = re.compile(r'\b([A-Z]{1,5})\b')


class NewsItem(BaseModel):
    title: str
    summary: str
    link: str
    published: str
    source: str
    tickers_mentioned: list[str]


class StockSnapshot(BaseModel):
    ticker: str
    price: Optional[float]
    change_pct: Optional[float]
    volume: Optional[int]
    market_cap: Optional[str]
    fetched_at: float


# Common English words to exclude from ticker false-positives
_STOP_WORDS = {
    "A", "I", "IN", "ON", "AT", "TO", "BY", "AS", "IS", "IT", "BE", "OR",
    "OF", "IF", "AN", "NO", "SO", "DO", "GO", "US", "UP", "MY", "HE", "WE",
    "ME", "HIM", "HER", "ITS", "THE", "FOR", "AND", "BUT", "NOT", "ARE",
    "WAS", "HAS", "HAD", "CAN", "MAY", "NEW", "SEC", "FED", "GDP", "CEO",
    "CFO", "IPO", "ETF", "NYSE", "OTC", "USA", "IMF", "WHO", "FDA", "ESG",
}


def _extract_tickers(text: str) -> list[str]:
    candidates = TICKER_PATTERN.findall(text or "")
    return sorted({c for c in candidates if c not in _STOP_WORDS})


def _parse_feed(source_key: str, url: str, limit: int) -> list[dict]:
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []

    items = []
    for entry in feed.entries[:limit]:
        title   = getattr(entry, "title",   "") or ""
        summary = getattr(entry, "summary", "") or ""
        link    = getattr(entry, "link",    "") or ""
        pub     = getattr(entry, "published","") or ""
        tickers = _extract_tickers(title + " " + summary)
        items.append({
            "title":             title,
            "summary":           summary[:500],
            "link":              link,
            "published":         pub,
            "source":            source_key,
            "tickers_mentioned": tickers,
        })
    return items


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", summary="Health check")
def root():
    """
    Health probe — used by the Dashboard node to verify this service is
    reachable over the Tailscale mesh network.
    """
    return {"service": "ingestion-node", "status": "ok"}


@app.get("/news", response_model=list[NewsItem], summary="Fetch financial news")
def get_news(
    source: NewsSource = Query(NewsSource.yahoo_finance, description="Feed key"),
    limit:  int        = Query(10, ge=1, le=50, description="Max articles to return"),
):
    """
    Fetches the latest financial news from the chosen RSS source.

    TAILSCALE CONCEPT — MagicDNS:
      The NLP node calls this endpoint as:
        http://ingestion-node.tail1ab2c.ts.net:8001/news
      Tailscale resolves that hostname to the node's private WireGuard IP
      automatically.  You never hard-code IP addresses.
    """
    feed_url = RSS_FEEDS[source]
    items = _parse_feed(source.value, feed_url, limit)
    return JSONResponse(content=items)


@app.get("/news/all", response_model=list[NewsItem], summary="Aggregate all feeds")
def get_all_news(limit_per_feed: int = Query(5, ge=1, le=20)):
    """Fetches from every registered RSS feed and merges results."""
    results = []
    for key, url in RSS_FEEDS.items():
        results.extend(_parse_feed(key.value, url, limit_per_feed))
    return JSONResponse(content=results)


_TICKER_VALID = re.compile(r'^[A-Z0-9\-\.]{1,10}$')

@app.get("/stock/{ticker}", response_model=StockSnapshot, summary="Market snapshot")
def get_stock(ticker: str):
    """
    Returns a current price snapshot for a single ticker using Yahoo Finance.

    TAILSCALE CONCEPT — Zero-trust access:
      Only nodes listed in the Tailscale ACL policy can call this endpoint.
      See tailscale_config/acl_policy.hujson for the rules.
    """
    ticker = ticker.upper()
    if not _TICKER_VALID.match(ticker):
        raise HTTPException(status_code=422, detail="Invalid ticker format")
    try:
        info = yf.Ticker(ticker).fast_info
        price      = getattr(info, "last_price",         None)
        change_pct = getattr(info, "regular_market_change_percent", None)
        volume     = getattr(info, "regular_market_volume", None)
        mkt_cap    = getattr(info, "market_cap",         None)
        if mkt_cap:
            mkt_cap = f"${mkt_cap / 1e9:.2f}B" if mkt_cap >= 1e9 else f"${mkt_cap / 1e6:.1f}M"
    except Exception:
        logger.warning("yfinance lookup failed for %s", ticker)
        price = change_pct = volume = mkt_cap = None

    return {
        "ticker":     ticker,
        "price":      price,
        "change_pct": change_pct,
        "volume":     volume,
        "market_cap": mkt_cap,
        "fetched_at": time.time(),
    }


@app.get("/feeds", summary="List available RSS feeds")
def list_feeds():
    return {"feeds": list(RSS_FEEDS.keys())}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("INGESTION_PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
