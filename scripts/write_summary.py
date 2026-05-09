"""Writes a Markdown summary to $GITHUB_STEP_SUMMARY."""
import json, os

with open("pipeline_result.json") as f:
    data = json.load(f)

counts  = data.get("counts", {})
results = data.get("results", [])
source  = data.get("source", "")
elapsed = data.get("elapsed_sec", 0)

lines = [
    "## Finance NLP Pipeline Results",
    "",
    "| Metric | Value |",
    "|--------|-------|",
    f"| Source | `{source}` |",
    f"| Articles fetched | {data.get('articles_in', 0)} |",
    f"| Articles analysed | {data.get('analyzed', 0)} |",
    f"| Elapsed | {elapsed}s |",
    "",
    "### Sentiment Breakdown",
    "| Label | Count |",
    "|-------|-------|",
    f"| Bullish | {counts.get('Bullish', 0)} |",
    f"| Bearish | {counts.get('Bearish', 0)} |",
    f"| Neutral | {counts.get('Neutral', 0)} |",
    "",
    "### Articles",
    "| Title | Sentiment | Score | Tickers |",
    "|-------|-----------|-------|---------|",
]

for r in results:
    s       = r.get("sentiment", {})
    e       = r.get("entities", {})
    label   = s.get("label", "Neutral")
    compound= s.get("compound", 0)
    tickers = ", ".join(e.get("tickers", [])[:4]) or "-"
    title   = r.get("title", "")[:80].replace("|", "-")
    link    = r.get("link", "")
    icon    = {"Bullish": "^", "Bearish": "v", "Neutral": "-"}.get(label, "-")
    t_cell  = f"[{title}]({link})" if link else title
    lines.append(f"| {t_cell} | {icon} {label} | `{compound:+.3f}` | {tickers} |")

summary_file = os.environ.get("GITHUB_STEP_SUMMARY", "step_summary.md")
with open(summary_file, "a") as f:
    f.write("\n".join(lines) + "\n")
print(f"Summary written to {summary_file}")
