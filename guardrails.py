"""
Two-stage guardrail applied BEFORE making any LLM API call.

Stage 1 — blocklist: explicit off-topic patterns, rejected immediately.
Stage 2 — allowlist: query must contain at least one ERP domain keyword.

Why this matters:
- Saves API quota for irrelevant queries
- Prevents prompt injection (e.g. "ignore all instructions and...")
- Provides a fast, deterministic response for clearly out-of-scope inputs
"""

DOMAIN_KEYWORDS = [
    "order", "delivery", "invoice", "billing", "payment", "customer",
    "material", "product", "journal", "shipment", "sales", "vendor",
    "quantity", "amount", "document", "flow", "status", "plant",
    "credit", "debit", "account", "fiscal", "cleared", "revenue",
    "goods", "dispatch", "receipt", "cancell", "partner", "entry",
    "so-", "je-", "bill-", "pay-", "del-", "cust-",
    "7405", "7406", "9400", "9150",   # common ID prefixes in this dataset
    "inr", "currency", "net amount", "total", "trace", "broken",
    "incomplete", "billed", "delivered", "shipped", "overdue",
    "business partner", "sold to", "ship to",
]

BLOCKLIST_PHRASES = [
    "write a poem", "tell me a joke", "recipe for", "capital of",
    "who is the president", "what is the weather", "movie recommendation",
    "song lyrics", "how to cook", "history of rome", "translate to",
    "what is 2+2", "ignore previous instructions", "forget your instructions",
    "pretend you are", "act as a", "you are now", "jailbreak",
    "write an essay", "explain quantum", "python tutorial",
    "stock market", "sports score", "news today",
]


def is_domain_query(query: str) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    reason is empty string on success, or a short explanation on rejection.
    """
    q = query.lower().strip()

    # Stage 1: explicit blocklist
    for phrase in BLOCKLIST_PHRASES:
        if phrase in q:
            return False, f"off-topic phrase detected: '{phrase}'"

    # Stage 2: must contain at least one domain keyword
    if any(kw in q for kw in DOMAIN_KEYWORDS):
        return True, ""

    # Very short queries (< 4 words) that passed blocklist get a pass —
    # they might be document IDs or single-word entity lookups
    if len(q.split()) <= 3:
        return True, ""

    return False, "no ERP domain terms detected in query"
