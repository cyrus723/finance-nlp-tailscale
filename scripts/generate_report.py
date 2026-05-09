"""Generates finance_nlp_report.html from pipeline_result.json."""
import json, html, datetime

with open("pipeline_result.json") as f:
    data = json.load(f)

results = data.get("results", [])
counts  = data.get("counts", {})
source  = data.get("source", "")
elapsed = data.get("elapsed_sec", 0)
now     = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

COLOR = {"Bullish": "#22c55e", "Bearish": "#ef4444", "Neutral": "#a3a3a3"}
ICON  = {"Bullish": "^", "Bearish": "v", "Neutral": "-"}

rows = ""
for r in results:
    s        = r.get("sentiment", {})
    e        = r.get("entities", {})
    label    = s.get("label", "Neutral")
    compound = s.get("compound", 0)
    tickers  = ", ".join(e.get("tickers", [])[:5]) or "-"
    t        = html.escape(r.get("title", ""))
    link     = html.escape(r.get("link", ""))
    src      = html.escape(r.get("source", ""))
    col      = COLOR.get(label, "#a3a3a3")
    icon     = ICON.get(label, "-")
    rows += (
        f"<tr>"
        f"<td><a href='{link}' target='_blank'>{t}</a>"
        f"<br><small style='color:#64748b'>{src}</small></td>"
        f"<td style='color:{col};font-weight:700'>{icon} {label}</td>"
        f"<td style='font-family:monospace'>{compound:+.3f}</td>"
        f"<td style='font-family:monospace;font-size:12px'>{tickers}</td>"
        f"</tr>"
    )

total = max(data.get("articles_in", 0), 1)
b_pct = round(counts.get("Bullish", 0) / total * 100)
r_pct = round(counts.get("Bearish", 0) / total * 100)
n_pct = round(counts.get("Neutral", 0) / total * 100)

page = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Finance NLP Report - {now}</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#0f1117;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#818cf8;font-size:20px}}
  h2{{color:#94a3b8;font-size:13px;font-weight:400;margin-top:4px}}
  .bar{{display:flex;height:14px;border-radius:99px;overflow:hidden;max-width:400px;margin:16px 0}}
  table{{width:100%;border-collapse:collapse;margin-top:20px;font-size:13px}}
  th{{text-align:left;padding:8px 12px;border-bottom:1px solid #2e3250;color:#64748b;font-weight:600;font-size:11px;text-transform:uppercase}}
  td{{padding:8px 12px;border-bottom:1px solid #1a1d27;vertical-align:top}}
  a{{color:#7dd3fc;text-decoration:none}}
</style></head>
<body>
<h1>Finance NLP Pipeline Report</h1>
<h2>Source: {source} | {data.get('analyzed',0)} articles | {elapsed}s | {now}</h2>
<div class="bar">
  <div style="width:{b_pct}%;background:#22c55e"></div>
  <div style="width:{r_pct}%;background:#ef4444"></div>
  <div style="width:{n_pct}%;background:#6b7280"></div>
</div>
<span style="color:#22c55e">^ {counts.get('Bullish',0)} Bullish ({b_pct}%)</span> &nbsp;
<span style="color:#ef4444">v {counts.get('Bearish',0)} Bearish ({r_pct}%)</span> &nbsp;
<span style="color:#a3a3a3">- {counts.get('Neutral',0)} Neutral ({n_pct}%)</span>
<table>
  <thead><tr><th>Article</th><th>Sentiment</th><th>Score</th><th>Tickers</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
</body></html>"""

with open("finance_nlp_report.html", "w") as f:
    f.write(page)
print("Report written to finance_nlp_report.html")
