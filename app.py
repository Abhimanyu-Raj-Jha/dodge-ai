"""
Flask application — production-ready API server.

Design decisions:
- Flask with threaded=True: each request gets its own thread; SQLite WAL mode
  handles concurrent reads safely without any additional locking.
- Graph built once at startup in a background thread; /api/graph returns cached JSON.
  Rebuilding 586 nodes is fast (~50ms) but we don't want it on every request.
- All routes return JSON except the frontend static files.
- /api/chat is synchronous (blocking). For true streaming you'd need SSE + a queue;
  the Gemini call takes ~2-4s which is acceptable for this use case.
- CORS is fully open — restrict to your Render domain in production.
"""
import json, threading, pathlib, os
from flask import Flask, jsonify, request, send_from_directory
from graph import build_graph, detect_broken_flows
from llm import chat
from guardrails import is_domain_query

# ── App setup ─────────────────────────────────────────────────────────────────
FRONTEND_DIR = pathlib.Path(__file__).parent
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")

# ── Graph cache ───────────────────────────────────────────────────────────────
_graph_cache: dict | None = None
_graph_lock  = threading.Lock()


def _warm_graph():
    """Pre-build graph on startup so first request is instant."""
    global _graph_cache
    try:
        g = build_graph()
        with _graph_lock:
            _graph_cache = g
        print(f"[startup] Graph ready: {g['summary']['total_nodes']} nodes, "
              f"{g['summary']['total_edges']} edges")
    except Exception as e:
        print(f"[startup] Graph build failed: {e}")


threading.Thread(target=_warm_graph, daemon=True).start()


def get_graph_cached() -> dict:
    global _graph_cache
    if _graph_cache is None:
        with _graph_lock:
            if _graph_cache is None:
                _graph_cache = build_graph()
    return _graph_cache


# ── CORS middleware ───────────────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/api/graph")
def api_graph():
    """Full graph for Cytoscape rendering."""
    return jsonify(get_graph_cached())


@app.route("/api/stats")
def api_stats():
    """
    Dashboard stats: row counts per table + broken flow count.
    Called once on page load to populate the stats panel.
    """
    import sqlite3
    db = pathlib.Path(__file__).parent / "data.db"
    conn = sqlite3.connect(str(db))

    tables = [
        "sales_order_headers", "billing_documents", "journal_entries",
        "payments", "business_partners", "outbound_delivery_headers",
        "sales_order_items",
    ]
    stats = {}
    for t in tables:
        try:
            stats[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            stats[t] = 0
    conn.close()

    # Broken flows is already computed efficiently in graph module
    broken = detect_broken_flows()
    stats["broken_flows"] = len(broken)
    stats["broken_flow_list"] = broken[:10]

    g = get_graph_cached()
    stats["graph_summary"] = g.get("summary", {})

    return jsonify(stats)


@app.route("/api/broken-flows")
def api_broken_flows():
    """Full list of broken O2C flows."""
    return jsonify(detect_broken_flows())


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def api_chat():
    if request.method == "OPTIONS":
        return "", 204

    body = request.get_json(force=True, silent=True) or {}
    message = (body.get("message") or "").strip()
    history = body.get("history") or []

    if not message:
        return jsonify({"error": "message is required"}), 400

    # Guardrail check before hitting the LLM
    allowed, reason = is_domain_query(message)
    if not allowed:
        return jsonify({
            "answer": "This system is designed to answer questions related to the provided ERP dataset only. "
                      "Please ask about sales orders, deliveries, billing documents, payments, customers, or products.",
            "sql": None, "results": [], "highlight_ids": [], "row_count": 0,
            "guardrail_blocked": True, "reason": reason
        })

    try:
        result = chat(message, history)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "answer": f"An error occurred processing your request: {str(e)}",
            "sql": None, "results": [], "highlight_ids": [], "row_count": 0
        }), 500


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "graph_loaded": _graph_cache is not None})


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """Serve the React/HTML frontend. SPA fallback to index.html."""
    target = FRONTEND_DIR / path
    if path and target.exists():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), "index.html")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Starting Dodge AI on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
