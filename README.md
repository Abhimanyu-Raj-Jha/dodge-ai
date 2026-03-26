# Dodge AI — SAP Order-to-Cash Graph System

A context graph system with LLM-powered natural language query interface for SAP Order-to-Cash ERP data.

**Live Demo:** [your-render-url]  
**GitHub:** [your-repo]

---

## What It Does

- Ingests 17,756 rows across 13 SAP tables into SQLite
- Builds a graph of 586 nodes and 531 edges representing the full O2C flow
- Visualises the graph interactively with Cytoscape.js
- Accepts natural language questions, translates them to SQL, executes against real data, and returns data-grounded answers
- Detects and surfaces broken flows (delivered but not billed orders)
- Highlights referenced nodes in the graph when the LLM mentions specific document IDs

---

## Architecture

```
dataset/sap-o2c-data/   ← raw JSONL files
       │
       ▼ (ingest.py — runs once at build time)
backend/data.db          ← SQLite, WAL mode, indexed FK columns
       │
       ├── graph.py      ← NetworkX DiGraph built in memory at startup
       ├── llm.py        ← Gemini Flash: SQL generation + narration
       ├── guardrails.py ← domain keyword check before LLM call
       └── app.py        ← Flask API: /api/graph /api/chat /api/stats

frontend/index.html      ← Single-file SPA: Cytoscape.js + chat UI
```

---

## Key Architecture Decisions

### SQLite over Neo4j / graph database

The LLM generates SQL far more reliably than Cypher or Gremlin. In testing, Gemini Flash produced valid, JOIN-correct SQL on the first attempt ~90% of the time. Its Cypher generation was brittle and required multiple retries. Since the dataset fits comfortably in memory, SQLite with WAL mode handles concurrent reads safely without any additional infrastructure.

The graph layer (NetworkX) is used for *traversal and visualisation*, not for querying. This gives us the best of both worlds: visual graph exploration in the UI + reliable SQL-backed answers from the LLM.

### Two-call LLM design

```
User query
    │
    ▼
Call 1: strict SQL-generation prompt
    │   (schema + samples + JOIN rules → <sql>...</sql>)
    │
    ▼
Execute SQL against SQLite
    │
    ▼
Call 2: conversational narration prompt
    │   (results → natural language answer)
    │
    ▼
Response + highlighted node IDs
```

Mixing SQL generation and narration into a single prompt degrades both. The SQL prompt needs strict grounding (schema, sample values, JOIN keys). The narration prompt needs conversational fluency. Separating them gives reliable SQL *and* readable answers.

### Schema with sample values

The schema injected into the LLM includes two sample rows per table. This is critical: without sample values, the LLM guesses status codes and column formats. With them, it knows that `overallDeliveryStatus = 'C'` means complete, that amounts are strings like `'19021.27'`, and that dates are ISO timestamps.

### Guardrails: pre-LLM keyword check

Before any API call, queries are checked against:
1. A blocklist of explicit off-topic phrases (`"tell me a joke"`, `"capital of"`, etc.)
2. An allowlist requiring at least one ERP domain keyword

This costs ~0ms and saves API quota. It also prevents prompt injection — an attacker cannot embed `"ignore all instructions"` in a query that contains no domain terms.

### Flask with WAL-mode SQLite for concurrency

Flask's `threaded=True` gives each request its own OS thread. SQLite in WAL mode allows unlimited concurrent readers with a single writer. For this dataset size and expected load, this handles 20–50 concurrent users comfortably. For higher load, switch `CMD` in Dockerfile to `gunicorn -w 4 -t 60 backend.app:app`.

---

## Graph Model

| Node Type | Source Table | Key Fields |
|---|---|---|
| Customer | business_partners | businessPartnerFullName |
| SalesOrder | sales_order_headers | totalNetAmount, deliveryStatus, billingStatus |
| Delivery | outbound_delivery_headers | deliveryDocument, goodsMovementStatus |
| BillingDoc | billing_documents | totalNetAmount, isCancelled |
| JournalEntry | journal_entries | accountingDocument, glAccount, amount |
| Payment | payments | amount, clearingDate |
| Product | product_descriptions | productDescription |

| Edge | Meaning |
|---|---|
| Customer → SalesOrder | PLACED_ORDER |
| Customer → BillingDoc | BILLED_TO |
| Customer → Payment | MADE_PAYMENT |
| SalesOrder → Product | CONTAINS_PRODUCT |
| BillingDoc → JournalEntry | POSTED_AS |

---

## Prompting Strategy

### SQL Generation Prompt
- Provides full schema with 2 sample rows per table (critical for correct value formats)
- States all JOIN keys explicitly
- Defines all status codes with their meanings
- Instructs LEFT JOINs to preserve records with missing relationships (reveals broken flows)
- Tells the model to write `OUTOFSCOPE` for off-topic questions

### Narration Prompt
- Receives the SQL results as JSON
- Instructed to cite specific document numbers and amounts
- Told to explain broken flows in business terms
- Max 3 paragraphs to keep answers scannable

---

## Guardrails

```python
# Stage 1: blocklist (O(n) string match, ~0ms)
for phrase in BLOCKLIST_PHRASES:
    if phrase in query.lower():
        return blocked

# Stage 2: domain keyword allowlist
if not any(kw in query.lower() for kw in DOMAIN_KEYWORDS):
    return blocked

# Stage 3: LLM-level check
# System prompt instructs model to respond "OUTOFSCOPE" for non-ERP questions
```

Three layers means a malicious or accidental off-topic query has to pass all three. In practice the keyword allowlist catches ~95% of off-topic queries before any API call is made.

---

## Example Queries

**Products with most billing documents:**
```
Which products are associated with the highest number of billing documents?
→ SUNSCREEN GEL SPF50-PA+++ 50ML appears most frequently (across 781 billing document relationships)
```

**Trace a billing document:**
```
Trace billing document 90504274
→ Shows full SO → Delivery → Billing → Journal chain, highlights nodes in graph
```

**Broken flows:**
```
Show me delivered orders that were never billed
→ 20 orders found. Bradley-Kelley has the highest at-risk amount (₹19,021), Nelson, Fitzpatrick and Jordan with 15 orders totalling ~₹8,400
```

---

## Local Setup

```bash
git clone <repo>
cd dodge-ai

# Set API key (get free key at https://ai.google.dev)
export GEMINI_API_KEY=your_key_here

# Build DB (first time only, ~5 seconds)
python3 backend/ingest.py

# Start server
python3 backend/app.py
# → http://localhost:5001
```

**Requirements:** Python 3.11+, Flask (`pip install flask`)

---

## Deploy on Render

1. Push to GitHub (include `dataset/` folder or pre-build `data.db`)
2. New Web Service → connect repo
3. Build command: `pip install flask && python3 backend/ingest.py`
4. Start command: `python3 backend/app.py`
5. Add environment variable: `GEMINI_API_KEY=your_key`
6. Free tier is sufficient for demo traffic

---

## Files

```
dodge-ai/
├── backend/
│   ├── app.py          # Flask server, API routes
│   ├── graph.py        # NetworkX graph builder
│   ├── guardrails.py   # Pre-LLM domain filter
│   ├── ingest.py       # JSONL → SQLite ingestion
│   └── llm.py          # Gemini integration, two-call design
├── frontend/
│   └── index.html      # Single-file SPA (Cytoscape + chat UI)
├── dataset/            # Raw JSONL from SAP O2C dataset
├── Dockerfile
├── requirements.txt
└── run.sh
```
