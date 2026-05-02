"""USD-per-million-token pricing for cost tracking in analysis.py.

Keep this conservative: when a model is missing we report cost as 0 and emit
a "missing_pricing" warning rather than guessing. Update the table when
Anthropic / OpenAI / Google publish new tiers.

Sources (rough, public list prices as of early 2026):
  - Anthropic: https://www.anthropic.com/pricing
  - OpenAI: https://openai.com/api/pricing/
  - Google: https://ai.google.dev/pricing
"""

from __future__ import annotations

PRICE_PER_M_TOKENS: dict[str, dict[str, float]] = {
    # Anthropic Claude
    "claude-haiku-4-5-20251001": {"in": 1.0, "out": 5.0},
    "claude-haiku-4-5":          {"in": 1.0, "out": 5.0},
    "claude-sonnet-4-6":         {"in": 3.0, "out": 15.0},
    "claude-opus-4-7":           {"in": 15.0, "out": 75.0},
    # Older Anthropic identifiers people still pin in .env
    "claude-3-5-sonnet-20241022": {"in": 3.0, "out": 15.0},
    "claude-3-5-haiku-20241022":  {"in": 0.8, "out": 4.0},
    # OpenAI
    "gpt-4o":      {"in": 2.5,  "out": 10.0},
    "gpt-4o-mini": {"in": 0.15, "out": 0.6},
    # Google
    "gemini-1.5-flash": {"in": 0.075, "out": 0.3},
    "gemini-1.5-pro":   {"in": 1.25,  "out": 5.0},
}


def cost_usd(model: str | None, input_tokens: int, output_tokens: int) -> float:
    """Return the USD cost of a (model, tokens) pair, or 0.0 if model unknown."""
    if not model:
        return 0.0
    p = PRICE_PER_M_TOKENS.get(model)
    if not p:
        return 0.0
    return round(
        (input_tokens / 1_000_000) * p["in"]
        + (output_tokens / 1_000_000) * p["out"],
        6,
    )


def is_priced(model: str | None) -> bool:
    return bool(model) and model in PRICE_PER_M_TOKENS
