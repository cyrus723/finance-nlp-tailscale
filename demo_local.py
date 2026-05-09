"""
demo_local.py - Single-machine Finance NLP demo
================================================
Runs all four services in background threads and executes one full pipeline
run without Docker or Tailscale.  Great for a quick first look.

Usage:
    pip install -r requirements.txt
    python demo_local.py

Then open http://localhost:8000 in your browser.
Press Ctrl+C to stop all services.

HOW TAILSCALE WOULD CHANGE THIS:
  Right now all four services share localhost.  With Tailscale you would start
  each service on its own machine; the only change is replacing "localhost" with
  the MagicDNS hostname in the environment variables below.
  Everything else — the service code, the pipeline logic — stays identical.
"""

import os
import sys
import time
import threading
import subprocess
import json
import textwrap
from pathlib import Path

# ── Service definitions ───────────────────────────────────────────────────────
ROOT = Path(__file__).parent

SERVICES = [
    {
        "name":    "ingestion-node",
        "tag":     "tag:ingestion",          # Tailscale tag (educational)
        "path":    ROOT / "services" / "ingestion",
        "module":  "main:app",
        "port":    8001,
        "env_key": "INGESTION_PORT",
    },
    {
        "name":    "nlp-node",
        "tag":     "tag:nlp",
        "path":    ROOT / "services" / "nlp_processor",
        "module":  "main:app",
        "port":    8002,
        "env_key": "NLP_PORT",
    },
    {
        "name":    "storage-node",
        "tag":     "tag:storage",
        "path":    ROOT / "services" / "storage",
        "module":  "main:app",
        "port":    8003,
        "env_key": "STORAGE_PORT",
    },
    {
        "name":    "dashboard-node",
        "tag":     "tag:dashboard",
        "path":    ROOT / "services" / "dashboard",
        "module":  "main:app",
        "port":    8000,
        "env_key": "DASHBOARD_PORT",
    },
]

_processes: list[subprocess.Popen] = []


def banner():
    print(textwrap.dedent("""
    +---------------------------------------------------------------+
    |       Finance NLP  -  Tailscale Mesh Pipeline Demo           |
    +---------------------------------------------------------------+

    This demo runs 4 microservices that would normally live on 4
    separate machines connected via Tailscale.  Here they all run
    on localhost so you can explore the code without any cloud setup.

    Tailscale benefit highlighted at each step:
      [ingestion-node]  -> MagicDNS replaces hardcoded IPs
      [nlp-node]        -> WireGuard encrypts all inter-node traffic
      [storage-node]    -> ACL policy controls who can write/read data
      [dashboard-node]  -> Funnel can expose this to the internet (HTTPS)

    """))


def start_service(svc: dict) -> subprocess.Popen:
    env = {**os.environ,
           svc["env_key"]: str(svc["port"]),
           "INGESTION_HOST": "localhost",
           "INGESTION_PORT": "8001",
           "NLP_HOST":       "localhost",
           "NLP_PORT":       "8002",
           "STORAGE_HOST":   "localhost",
           "STORAGE_PORT":   "8003",
           "DASHBOARD_PORT": "8000"}

    cmd = [
        sys.executable, "-m", "uvicorn", svc["module"],
        "--host", "0.0.0.0",
        "--port", str(svc["port"]),
        "--log-level", "warning",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(svc["path"]),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    return proc


def wait_for_service(name: str, port: int, timeout: int = 30) -> bool:
    import urllib.request, urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def run_demo_pipeline():
    """Calls the dashboard's /api/run endpoint and prints a pretty report."""
    import urllib.request, json as _json
    try:
        with urllib.request.urlopen(
            "http://localhost:8000/api/run?source=yahoo_finance&limit=8",
            timeout=60,
        ) as resp:
            data = _json.loads(resp.read())
    except Exception as exc:
        print(f"\n  [!] Pipeline call failed: {exc}")
        return

    results = data.get("results", [])
    counts  = data.get("counts", {})
    elapsed = data.get("elapsed_sec", "?")

    print(f"\n  {'-'*63}")
    print(f"  Pipeline complete in {elapsed}s  |  "
          f"Articles: {data.get('articles_in',0)}  |  "
          f"Analysed: {data.get('analyzed',0)}")
    print(f"  Bullish: {counts.get('Bullish',0)}  "
          f"Bearish: {counts.get('Bearish',0)}  "
          f"Neutral: {counts.get('Neutral',0)}")
    print(f"  {'-'*63}\n")

    for r in results[:5]:
        s = r.get("sentiment", {})
        e = r.get("entities", {})
        label    = s.get("label", "Neutral")
        compound = s.get("compound", 0)
        tickers  = ", ".join(e.get("tickers", [])[:4]) or "-"
        amounts  = ", ".join(e.get("amounts", [])[:3]) or ""

        label_icon = {"Bullish": "^", "Bearish": "v", "Neutral": "-"}.get(label, "-")
        title = r["title"][:70] + ("..." if len(r["title"]) > 70 else "")
        print(f"  {label_icon} [{label:<7}  {compound:+.3f}]  {title}")
        print(f"      Tickers: {tickers}{'  Amounts: ' + amounts if amounts else ''}")
        print()

    if len(results) > 5:
        print(f"  ... and {len(results)-5} more.  See http://localhost:8000 for the full view.\n")


def main():
    banner()

    # Start services
    print("  Starting services...\n")
    for svc in SERVICES:
        proc = start_service(svc)
        _processes.append(proc)

        ok = wait_for_service(svc["name"], svc["port"])
        ts_note = f"(Tailscale would tag this as {svc['tag']})"
        status  = "[online]" if ok else "[timeout]"
        print(f"    {status:12}  {svc['name']:20}  http://localhost:{svc['port']}  {ts_note}")

    print()

    # Run demo pipeline
    print("  Running demo pipeline: Ingestion -> NLP -> Storage ...")
    print("  (In Tailscale mode each arrow would cross an encrypted WireGuard tunnel)\n")
    run_demo_pipeline()

    # Dashboard URL
    print("  +---------------------------------------------------------+")
    print("  |  Dashboard  ->  http://localhost:8000                   |")
    print("  |  API docs   ->  http://localhost:8000/docs              |")
    print("  |                                                         |")
    print("  |  Tailscale tip: run `tailscale funnel 8000` on the     |")
    print("  |  dashboard machine to get a public HTTPS URL instantly. |")
    print("  +---------------------------------------------------------+")
    print("\n  Press Ctrl+C to stop all services.\n")

    # ── Keep alive ────────────────────────────────────────────────────────────
    try:
        while True:
            time.sleep(1)
            for proc in _processes:
                if proc.poll() is not None:
                    err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
                    print(f"\n  [!] A service exited unexpectedly:\n{err}")
    except KeyboardInterrupt:
        print("\n\n  Stopping services…")
        for proc in _processes:
            proc.terminate()
        print("  Done. Goodbye!\n")


if __name__ == "__main__":
    main()
