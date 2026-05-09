"""
Finance-tuned sentiment analysis using VADER with financial keyword boosters.

VADER (Valence Aware Dictionary and sEntiment Reasoner) works out-of-the-box
for short texts like news headlines. We extend it with a finance-specific
lexicon so that words like "bullish", "downgrade", "beat estimates" score
correctly instead of being treated as neutral.
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Finance-specific lexicon boosters (score range: -4.0 to +4.0)
FINANCE_LEXICON: dict[str, float] = {
    # Strongly bullish
    "bullish":          3.5,
    "beat":             2.8,
    "outperform":       3.0,
    "upgrade":          2.5,
    "buy":              2.0,
    "record high":      3.5,
    "all-time high":    3.5,
    "rally":            2.5,
    "surge":            3.0,
    "soar":             3.2,
    "breakout":         2.5,
    "dividend":         1.5,
    "buyback":          2.0,
    "beat estimates":   3.5,
    "strong earnings":  3.5,
    "guidance raised":  3.0,
    # Mildly bullish
    "growth":           1.0,
    "profit":           1.2,
    "gain":             1.5,
    "positive":         1.0,
    "recovery":         1.2,
    # Mildly bearish
    "miss":            -2.0,
    "concern":         -1.2,
    "risk":            -1.0,
    "decline":         -1.5,
    "lower":           -0.8,
    # Strongly bearish
    "bearish":         -3.5,
    "downgrade":       -3.0,
    "underperform":    -2.5,
    "sell":            -2.0,
    "plunge":          -3.2,
    "crash":           -3.5,
    "default":         -3.5,
    "bankruptcy":      -4.0,
    "layoff":          -2.5,
    "layoffs":         -2.5,
    "recession":       -3.0,
    "miss estimates":  -3.5,
    "guidance cut":    -3.0,
    "write-down":      -2.8,
    "investigation":   -2.5,
    "lawsuit":         -2.0,
    "fraud":           -4.0,
    "loss":            -1.8,
    "losses":          -2.0,
}


class FinanceSentimentAnalyzer:
    def __init__(self):
        self._vader = SentimentIntensityAnalyzer()
        # Inject finance lexicon into VADER's dictionary
        self._vader.lexicon.update(FINANCE_LEXICON)

    def analyze(self, text: str) -> dict:
        """
        Returns a sentiment dict:
          compound : float  [-1.0, +1.0]  overall polarity
          positive : float  [0.0, 1.0]    proportion positive
          negative : float  [0.0, 1.0]    proportion negative
          neutral  : float  [0.0, 1.0]    proportion neutral
          label    : str    "Bullish" | "Bearish" | "Neutral"
        """
        scores = self._vader.polarity_scores(text or "")
        compound = scores["compound"]

        if compound >= 0.05:
            label = "Bullish"
        elif compound <= -0.05:
            label = "Bearish"
        else:
            label = "Neutral"

        return {
            "compound": round(compound, 4),
            "positive": round(scores["pos"], 4),
            "negative": round(scores["neg"], 4),
            "neutral":  round(scores["neu"], 4),
            "label":    label,
        }

    def batch_analyze(self, texts: list[str]) -> list[dict]:
        return [self.analyze(t) for t in texts]
