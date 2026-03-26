"""
LLM integration — OpenRouter with open-source models (free tier).

Architecture: two-call design
  Call 1 (SQL generation): strict technical prompt → SQL between <sql> tags
  Call 2 (narration): conversational prompt → natural language answer

Why two calls instead of one?
- A single prompt trying to do both SQL and narrative degrades at both.
  The SQL prompt needs strict schema-grounding; the narrative prompt needs
  conversational fluency. Separating them gives reliable SQL + readable answers.

Conversation memory: last 6 turns (3 exchanges) injected into Call 1.
This lets users say "now filter that by customer X" without repeating context.

Uses only Python stdlib (urllib) — no extra dependencies.
"""
import sqlite3, re, json, os, pathlib, urllib.request, urllib.error, time

DB_PATH  = pathlib.Path(__file__).parent / "data.db"
API_KEY  = os.environ.get("OPENROUTER_API_KEY", "")

# Using Meta's Llama 3.1 70B via OpenRouter (or fallback to Mistral)
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-3.5-turbo"  # Available model on OpenRouter

_schema_cache: str | None = None


def get_schema() -> str:
    global _schema_cache
    if _schema_cache:
        return _schema_cache

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    skip = {"product_storage_locations", "product_plants"}  # large, low-query-value tables
    parts = []

    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ):
        t = row[0]
        if t in skip:
            continue
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        # Two sample rows give the LLM realistic values for WHERE clause generation
        samples = conn.execute(f"SELECT * FROM {t} LIMIT 2").fetchall()
        sample_strs = []
        for s in samples:
            d = {k: v for k, v in dict(s).items() if v not in (None, "", "None")}
            sample_strs.append(json.dumps(d)[:250])
        parts.append(
            f"TABLE {t}:\n"
            f"  columns: {', '.join(cols)}\n"
            f"  samples: {' | '.join(sample_strs)}"
        )
    conn.close()
    _schema_cache = "\n\n".join(parts)
    return _schema_cache


SQL_SYSTEM_TEMPLATE = """You are an expert SQL analyst for a SAP Order-to-Cash (O2C) ERP dataset.

STRICT RULES:
1. You ONLY answer questions about this ERP dataset. If the question is unrelated to ERP, orders,
   deliveries, billing, payments, customers, or products, respond with exactly: OUTOFSCOPE
2. Always put your SQL query between <sql> and </sql> tags.
3. Use only the tables listed below — do not hallucinate table or column names.
4. Cap results with LIMIT 50 unless the user asks for more.
5. Use LEFT JOINs to preserve records even when related documents are missing (this reveals broken flows).
6. Never guess column values — look at the sample data to understand actual values used.

DATABASE SCHEMA (with sample data):
{schema}

CRITICAL JOIN KEYS:
- sales_order_headers.salesOrder  ↔  sales_order_items.salesOrder
- sales_order_headers.soldToParty ↔  business_partners.customer
- billing_documents.soldToParty   ↔  business_partners.customer
- billing_documents.billingDocument ↔ journal_entries.referenceDocument
- billing_documents.accountingDocument ↔ journal_entries.accountingDocument
- payments.customer               ↔  business_partners.customer
- sales_order_items.material      ↔  product_descriptions.product

BROKEN FLOW DETECTION:
- Delivered but not billed: overallDeliveryStatus = 'C' AND overallOrdReltdBillgStatus IN ('', NULL)
- Billing document cancelled: billingDocumentIsCancelled = 'True'
- Payment without billing: payments with no matching billing_documents row

STATUS CODES:
- overallDeliveryStatus: 'A'=not started, 'B'=partial, 'C'=complete
- overallOrdReltdBillgStatus: ''=not billed, 'B'=partial, 'C'=complete
- overallGoodsMovementStatus: 'A'=not started, 'B'=partial, 'C'=complete
"""

NARRATE_SYSTEM = """You are a concise, expert ERP analyst assistant for an Order-to-Cash process.

Given a user question and SQL query results, write a clear natural language answer.

Rules:
- Be direct. Lead with the answer, then supporting details.
- Cite specific values (document numbers, amounts, customer names) from the results.
- If the result set is empty, say so clearly and explain what that likely means.
- For broken flows, explain the business risk.
- Max 3 short paragraphs. No bullet lists unless there are 3+ items.
- Never mention SQL, tables, columns, or technical implementation.
- If results were truncated, note that only the top N results are shown.
"""


def _call_openrouter(messages: list[dict], max_tokens: int = 1500) -> str:
    if not API_KEY:
        return "ERROR: OPENROUTER_API_KEY environment variable is not set. Please set it and restart."

    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.1,  # low temp for SQL accuracy
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
        
        if "error" in data:
            return f"OpenRouter API error: {data['error'].get('message', 'Unknown error')}"
        
        choices = data.get("choices", [])
        if not choices:
            return f"No response from model. Raw: {json.dumps(data)[:300]}"
        
        return choices[0].get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"OpenRouter API error {e.code}: {body[:400]}"
    except urllib.error.URLError as e:
        return f"Network error: {e.reason}"
    except Exception as e:
        return f"Unexpected error: {e}"


def run_sql(sql: str) -> tuple[list[dict], str | None]:
    """Returns (rows, error_message). error_message is None on success."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Safety: only allow SELECT statements
    sql_stripped = sql.strip().upper()
    if not sql_stripped.startswith("SELECT") and not sql_stripped.startswith("WITH"):
        return [], "Only SELECT queries are permitted."
    try:
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        return rows, None
    except sqlite3.Error as e:
        return [], str(e)
    finally:
        conn.close()


def _extract_highlight_ids(text: str) -> list[str]:
    """
    Parse any document IDs mentioned in the answer and map them
    to Cytoscape node IDs so the frontend can highlight them.
    """
    ids = set()
    # Sales orders: 6-digit numbers starting with 740xxx
    for m in re.findall(r'\b(740\d{3})\b', text):
        ids.add(f"SO_{m}")
    # Billing docs: start with 905/906 and are 8-9 digits
    for m in re.findall(r'\b(9[05]\d{6,7})\b', text):
        ids.add(f"BILL_{m}")
    # Journal entries / accounting docs: start with 9400
    for m in re.findall(r'\b(9400\d{5,7})\b', text):
        ids.add(f"JE_{m}")  # partial match; graph uses JE_{doc}_{item}
    # Deliveries: start with 807
    for m in re.findall(r'\b(807\d{5})\b', text):
        ids.add(f"DEL_{m}")
    # Customer IDs
    for m in re.findall(r'\b(3[12]0\d{6})\b', text):
        ids.add(f"CUST_{m}")
    return list(ids)[:20]  # cap at 20 highlights


def chat(user_message: str, history: list[dict]) -> dict:
    """
    Main entry point for the chat API.

    Returns:
        {
          "answer": str,           # natural language response
          "sql": str | None,       # the SQL that was executed (for transparency)
          "results": list[dict],   # raw query results (shown in UI)
          "highlight_ids": list,   # graph node IDs to highlight
          "row_count": int
        }
    """
    schema = get_schema()
    system_text = SQL_SYSTEM_TEMPLATE.format(schema=schema)

    # Build OpenRouter messages array (standard OpenAI format)
    messages = [
        {"role": "system", "content": system_text},
    ]

    # Inject conversation memory (last 3 exchanges = 6 turns)
    for turn in history[-6:]:
        role = "user" if turn.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": turn["content"]})

    messages.append({"role": "user", "content": user_message})

    # ── Call 1: SQL generation ────────────────────────────────────────────────
    sql_response = _call_openrouter(messages, max_tokens=800)

    if "OUTOFSCOPE" in sql_response:
        return {
            "answer": "This system is designed to answer questions related to the provided ERP dataset only. Please ask about orders, deliveries, billing, payments, customers, or products.",
            "sql": None, "results": [], "highlight_ids": [], "row_count": 0
        }

    if sql_response.startswith("ERROR:") or sql_response.startswith("OpenRouter API error"):
        return {
            "answer": f"⚠️ {sql_response}",
            "sql": None, "results": [], "highlight_ids": [], "row_count": 0
        }

    # Extract SQL from response
    sql_match = re.search(r'<sql>(.*?)</sql>', sql_response, re.DOTALL | re.IGNORECASE)

    executed_sql = None
    results = []
    sql_error = None

    if sql_match:
        executed_sql = sql_match.group(1).strip()
        results, sql_error = run_sql(executed_sql)

        if sql_error:
            # Ask model to fix the SQL once
            fix_messages = messages + [
                {"role": "assistant", "content": sql_response},
                {"role": "user", "content": f"That SQL produced an error: {sql_error}. Please fix it and provide corrected SQL between <sql> tags."}
            ]
            fix_response = _call_openrouter(fix_messages, max_tokens=600)
            fix_match = re.search(r'<sql>(.*?)</sql>', fix_response, re.DOTALL | re.IGNORECASE)
            if fix_match:
                executed_sql = fix_match.group(1).strip()
                results, sql_error = run_sql(executed_sql)

    # ── Call 2: Narrate results ────────────────────────────────────────────────
    if sql_match:
        result_preview = results[:30] if results else []
        narrate_prompt = (
            f"User question: {user_message}\n\n"
            f"Query returned {len(results)} rows. "
            f"{'(Showing first 30)' if len(results) > 30 else ''}\n"
            f"Results:\n{json.dumps(result_preview, indent=2)}\n\n"
            + (f"SQL error occurred: {sql_error}\n\n" if sql_error else "")
            + "Write a clear, concise answer based only on these results."
        )
        narrate_messages = [
            {"role": "system", "content": NARRATE_SYSTEM},
            {"role": "user", "content": narrate_prompt}
        ]
        answer = _call_openrouter(narrate_messages, max_tokens=600)
    else:
        # LLM answered directly (schema question, clarification, etc.)
        answer = sql_response
        # Strip any accidental SQL or system-prompt leakage
        answer = re.sub(r'<sql>.*?</sql>', '', answer, flags=re.DOTALL).strip()

    # Extract node IDs to highlight in graph
    highlight_ids = _extract_highlight_ids(answer + (executed_sql or ""))

    return {
        "answer": answer,
        "sql": executed_sql,
        "results": results[:50],
        "highlight_ids": highlight_ids,
        "row_count": len(results)
    }
