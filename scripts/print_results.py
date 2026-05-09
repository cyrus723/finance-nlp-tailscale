"""Prints pipeline result summary to stdout (called from GitHub Actions)."""
import json, sys

with open("pipeline_result.json") as f:
    data = json.load(f)

c = data.get("counts", {})
print(f"Articles fetched : {data.get('articles_in', 0)}")
print(f"Articles analysed: {data.get('analyzed', 0)}")
print(f"Elapsed          : {data.get('elapsed_sec', 0)}s")
print(f"Bullish: {c.get('Bullish',0)}  Bearish: {c.get('Bearish',0)}  Neutral: {c.get('Neutral',0)}")
print()
for r in data.get("results", []):
    s = r.get("sentiment", {})
    e = r.get("entities", {})
    label    = s.get("label", "Neutral")
    compound = s.get("compound", 0)
    tickers  = ", ".join(e.get("tickers", [])[:4]) or "-"
    title    = r.get("title", "")[:80]
    icon     = {"Bullish": "^", "Bearish": "v", "Neutral": "-"}.get(label, "-")
    print(f"  {icon} [{label:<7} {compound:+.3f}]  {title}")
    if tickers != "-":
        print(f"      Tickers: {tickers}")
