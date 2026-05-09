"""
Database models and SQLite helpers for the Storage node.

SQLite is used here for zero-dependency simplicity. In production you would
point Tailscale's subnet router at your PostgreSQL cluster and all nodes reach
it by internal hostname without any firewall changes.
"""

import os
import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "finance_nlp.db")))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)  # Restrict DB file to owner only
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                title         TEXT    NOT NULL,
                summary       TEXT,
                link          TEXT,
                published     TEXT,
                source        TEXT,
                ingested_at   REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id      INTEGER REFERENCES articles(id),
                sentiment_label TEXT,
                compound        REAL,
                positive        REAL,
                negative        REAL,
                neutral         REAL,
                tickers         TEXT,   -- JSON array
                companies       TEXT,   -- JSON array
                amounts         TEXT,   -- JSON array
                percentages     TEXT,   -- JSON array
                dates           TEXT,   -- JSON array
                processed_at    REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS run_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at      REAL    NOT NULL,
                source      TEXT,
                articles_in INTEGER,
                analyzed    INTEGER,
                bullish     INTEGER,
                bearish     INTEGER,
                neutral     INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_analyses_label
                ON analyses(sentiment_label);
            CREATE INDEX IF NOT EXISTS idx_articles_source
                ON articles(source);
        """)


# ── CRUD helpers ───────────────────────────────────────────────────────────────

def insert_article(data: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO articles (title, summary, link, published, source, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["title"], data.get("summary"), data.get("link"),
             data.get("published"), data.get("source"), time.time()),
        )
        return cur.lastrowid


def insert_analysis(article_id: int, nlp: dict) -> int:
    s = nlp.get("sentiment", {})
    e = nlp.get("entities",  {})
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO analyses
               (article_id, sentiment_label, compound, positive, negative, neutral,
                tickers, companies, amounts, percentages, dates, processed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                article_id,
                s.get("label"),
                s.get("compound"),
                s.get("positive"),
                s.get("negative"),
                s.get("neutral"),
                json.dumps(e.get("tickers",     [])),
                json.dumps(e.get("companies",   [])),
                json.dumps(e.get("amounts",     [])),
                json.dumps(e.get("percentages", [])),
                json.dumps(e.get("dates",       [])),
                time.time(),
            ),
        )
        return cur.lastrowid


def log_run(data: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO run_log (run_at, source, articles_in, analyzed, bullish, bearish, neutral)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), data.get("source"), data.get("articles_in", 0),
             data.get("analyzed", 0), data.get("bullish", 0),
             data.get("bearish", 0), data.get("neutral", 0)),
        )


def query_recent(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.title, a.link, a.source, a.published,
                      n.sentiment_label, n.compound, n.tickers, n.companies
               FROM articles a
               JOIN analyses n ON n.article_id = a.id
               ORDER BY n.processed_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def query_sentiment_summary() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) AS total,
                   SUM(CASE WHEN sentiment_label='Bullish' THEN 1 ELSE 0 END) AS bullish,
                   SUM(CASE WHEN sentiment_label='Bearish' THEN 1 ELSE 0 END) AS bearish,
                   SUM(CASE WHEN sentiment_label='Neutral' THEN 1 ELSE 0 END) AS neutral,
                   AVG(compound) AS avg_compound
               FROM analyses"""
        ).fetchone()
    d = dict(row)
    total = d["total"] or 1
    d["bullish_pct"] = round((d["bullish"] or 0) / total * 100, 1)
    d["bearish_pct"] = round((d["bearish"] or 0) / total * 100, 1)
    d["neutral_pct"] = round((d["neutral"] or 0) / total * 100, 1)
    d["avg_compound"] = round(d["avg_compound"] or 0.0, 4)
    return d


def query_top_tickers(limit: int = 10) -> list[dict]:
    """Count ticker mentions across all analyses."""
    with get_conn() as conn:
        rows = conn.execute("SELECT tickers FROM analyses WHERE tickers != '[]'").fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        for ticker in json.loads(row["tickers"]):
            counts[ticker] = counts.get(ticker, 0) + 1

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"ticker": t, "mentions": c} for t, c in sorted_items[:limit]]
