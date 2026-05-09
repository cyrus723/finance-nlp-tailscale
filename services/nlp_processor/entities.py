"""
Financial entity extraction — tickers, companies, monetary values, percentages.

Uses regex + a curated S&P 500 company-to-ticker map.  No external model
needed: fast, deterministic, and runs on the NLP node inside the Tailscale
mesh with zero internet egress.
"""

import re
from dataclasses import dataclass

# ── Curated company → ticker mapping (top-50 by market cap) ──────────────────
COMPANY_MAP: dict[str, str] = {
    "apple":          "AAPL",  "microsoft":    "MSFT",  "nvidia":       "NVDA",
    "amazon":         "AMZN",  "alphabet":     "GOOGL", "google":       "GOOGL",
    "meta":           "META",  "berkshire":    "BRK-B", "tesla":        "TSLA",
    "broadcom":       "AVGO",  "jpmorgan":     "JPM",   "jp morgan":    "JPM",
    "eli lilly":      "LLY",   "walmart":      "WMT",   "visa":         "V",
    "unitedhealth":   "UNH",   "exxon":        "XOM",   "mastercard":   "MA",
    "procter":        "PG",    "costco":        "COST", "johnson":      "JNJ",
    "oracle":         "ORCL",  "home depot":   "HD",    "chevron":      "CVX",
    "abbott":         "ABT",   "merck":        "MRK",   "salesforce":   "CRM",
    "netflix":        "NFLX",  "adobe":        "ADBE",  "amd":          "AMD",
    "intel":          "INTC",  "qualcomm":     "QCOM",  "paypal":       "PYPL",
    "shopify":        "SHOP",  "spotify":      "SPOT",  "coinbase":     "COIN",
    "palantir":       "PLTR",  "snowflake":    "SNOW",  "uber":         "UBER",
    "airbnb":         "ABNB",  "block":        "SQ",    "square":       "SQ",
    "robinhood":      "HOOD",  "rivian":       "RIVN",  "lucid":        "LCID",
    "nio":            "NIO",   "arm":          "ARM",   "openai":       None,
    "anthropic":      None,
}

# Patterns
_TICKER_RE  = re.compile(r'\b([A-Z]{1,5})\b')
_MONEY_RE   = re.compile(r'\$[\d,.]+[BMK]?(?:\s?(?:billion|million|trillion))?', re.I)
_PCT_RE     = re.compile(r'[-+]?\d+\.?\d*\s*%')
_DATE_RE    = re.compile(
    r'\b(?:Q[1-4]\s?\d{4}|\d{4}\s?(?:fiscal|FY)?|'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b',
    re.I,
)

_STOP_WORDS = {
    "A","I","IN","ON","AT","TO","BY","AS","IS","IT","BE","OR","OF","IF","AN",
    "NO","SO","DO","GO","US","UP","MY","HE","WE","ME","HIM","HER","ITS","THE",
    "FOR","AND","BUT","NOT","ARE","WAS","HAS","HAD","CAN","MAY","NEW","SEC",
    "FED","GDP","CEO","CFO","IPO","ETF","NYSE","OTC","USA","IMF","WHO","FDA",
    "ESG","AI","EV","PE","ROI","YOY","QOQ","TTM","EPS","PEG","RSI","ATH",
}


@dataclass
class FinanceEntities:
    tickers:    list[str]
    companies:  list[str]
    amounts:    list[str]
    percentages: list[str]
    dates:      list[str]


def extract(text: str) -> FinanceEntities:
    """Extract all financial entities from a text string."""
    lower = (text or "").lower()

    # Company names → canonical tickers
    found_companies: list[str] = []
    found_tickers_from_company: list[str] = []
    for name, ticker in COMPANY_MAP.items():
        if name in lower:
            found_companies.append(name.title())
            if ticker:
                found_tickers_from_company.append(ticker)

    # Raw ticker tokens (ALL-CAPS 1-5 letters)
    raw_tickers = [t for t in _TICKER_RE.findall(text or "")
                   if t not in _STOP_WORDS]

    all_tickers = sorted(set(found_tickers_from_company + raw_tickers))

    return FinanceEntities(
        tickers=    all_tickers,
        companies=  sorted(set(found_companies)),
        amounts=    _MONEY_RE.findall(text or ""),
        percentages=_PCT_RE.findall(text or ""),
        dates=      _DATE_RE.findall(text or ""),
    )


def extract_as_dict(text: str) -> dict:
    e = extract(text)
    return {
        "tickers":     e.tickers,
        "companies":   e.companies,
        "amounts":     e.amounts,
        "percentages": e.percentages,
        "dates":       e.dates,
    }
