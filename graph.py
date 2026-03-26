"""
Graph construction: builds a NetworkX DiGraph from SQLite at startup, cached in memory.

Why in-memory NetworkX over a graph DB:
- Zero infrastructure; the dataset fits easily in RAM (~17k rows)
- Path traversal and broken-flow detection are simple Python set operations
- The serialised Cytoscape JSON is computed once and served statically after that

Node types and their colors match the Dodge AI reference UI:
  Customer → green, SalesOrder → purple, Delivery → blue,
  BillingDoc → amber, JournalEntry → coral, Payment → pink, Product → teal
"""
import sqlite3, pathlib

DB_PATH = pathlib.Path(__file__).parent / "data.db"

NODE_META = {
    "Customer":    {"color": "#1D9E75", "size": 20},
    "SalesOrder":  {"color": "#7F77DD", "size": 16},
    "Delivery":    {"color": "#378ADD", "size": 14},
    "BillingDoc":  {"color": "#BA7517", "size": 14},
    "JournalEntry":{"color": "#D85A30", "size": 12},
    "Payment":     {"color": "#993556", "size": 12},
    "Product":     {"color": "#0F6E56", "size": 12},
}


def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def build_graph() -> dict:
    """
    Returns Cytoscape-ready JSON: {"nodes": [...], "edges": [...]}
    Each node: {"data": {"id", "type", "label", "color", "size", ...fields}}
    Each edge: {"data": {"id", "source", "target", "relation"}}
    """
    conn = _conn()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_set: set[tuple] = set()  # deduplicate edges

    def add_node(nid: str, ntype: str, label: str, extra: dict | None = None):
        if nid not in nodes:
            meta = NODE_META.get(ntype, {"color": "#888780", "size": 12})
            nodes[nid] = {
                "id": nid, "type": ntype, "label": label,
                "color": meta["color"], "size": meta["size"],
                **(extra or {})
            }

    def add_edge(src: str, tgt: str, rel: str):
        key = (src, tgt, rel)
        if key not in edge_set and src in nodes and tgt in nodes:
            edge_set.add(key)
            edges.append({"source": src, "target": tgt, "relation": rel})

    # ── Customers ─────────────────────────────────────────────────────────────
    for r in conn.execute(
        "SELECT customer, businessPartnerFullName FROM business_partners"
    ):
        nid = f"CUST_{r['customer']}"
        add_node(nid, "Customer",
                 r["businessPartnerFullName"] or r["customer"],
                 {"customerId": r["customer"]})

    # ── Sales Orders ──────────────────────────────────────────────────────────
    for r in conn.execute("SELECT * FROM sales_order_headers"):
        nid = f"SO_{r['salesOrder']}"
        add_node(nid, "SalesOrder", f"SO-{r['salesOrder']}", {
            "salesOrder": r["salesOrder"],
            "totalNetAmount": r["totalNetAmount"],
            "currency": r["transactionCurrency"],
            "deliveryStatus": r["overallDeliveryStatus"],
            "billingStatus": r["overallOrdReltdBillgStatus"],
            "creationDate": r["creationDate"],
        })
        cust = f"CUST_{r['soldToParty']}"
        add_edge(cust, nid, "PLACED_ORDER")

    # ── Sales Order Items → Products ──────────────────────────────────────────
    # Build product name lookup first
    prod_names = {}
    for r in conn.execute(
        "SELECT product, productDescription FROM product_descriptions "
        "WHERE language='E' OR language='EN' OR language='en'"
    ):
        prod_names[r["product"]] = r["productDescription"]

    for r in conn.execute("SELECT * FROM sales_order_items"):
        so_nid = f"SO_{r['salesOrder']}"
        prod_nid = f"PROD_{r['material']}"
        name = prod_names.get(r["material"], r["material"])
        add_node(prod_nid, "Product", name[:40] if name else r["material"], {
            "material": r["material"],
        })
        # SO → Product edge (deduplicated automatically via edge_set)
        add_edge(so_nid, prod_nid, "CONTAINS_PRODUCT")

    # ── Deliveries ────────────────────────────────────────────────────────────
    for r in conn.execute("SELECT * FROM outbound_delivery_headers"):
        nid = f"DEL_{r['deliveryDocument']}"
        add_node(nid, "Delivery", f"DEL-{r['deliveryDocument']}", {
            "deliveryDocument": r["deliveryDocument"],
            "shippingPoint": r["shippingPoint"],
            "goodsMovementStatus": r["overallGoodsMovementStatus"],
            "pickingStatus": r["overallPickingStatus"],
            "creationDate": r["creationDate"],
        })

    # ── Billing Documents ─────────────────────────────────────────────────────
    for r in conn.execute("SELECT * FROM billing_documents"):
        nid = f"BILL_{r['billingDocument']}"
        add_node(nid, "BillingDoc", f"BILL-{r['billingDocument']}", {
            "billingDocument": r["billingDocument"],
            "totalNetAmount": r["totalNetAmount"],
            "currency": r["transactionCurrency"],
            "billingDate": r["billingDocumentDate"],
            "isCancelled": r["billingDocumentIsCancelled"],
            "accountingDocument": r["accountingDocument"],
        })
        cust_nid = f"CUST_{r['soldToParty']}"
        add_edge(cust_nid, nid, "BILLED_TO")

    # ── Journal Entries ───────────────────────────────────────────────────────
    for r in conn.execute("SELECT * FROM journal_entries"):
        nid = f"JE_{r['accountingDocument']}_{r['accountingDocumentItem']}"
        add_node(nid, "JournalEntry", f"JE-{r['accountingDocument']}", {
            "accountingDocument": r["accountingDocument"],
            "referenceDocument": r["referenceDocument"],
            "amount": r["amountInTransactionCurrency"],
            "currency": r["transactionCurrency"],
            "postingDate": r["postingDate"],
            "glAccount": r["glAccount"],
            "customer": r["customer"],
            "fiscalYear": r["fiscalYear"],
        })
        # Journal Entry → Billing Doc via referenceDocument
        bill_nid = f"BILL_{r['referenceDocument']}"
        if bill_nid in nodes:
            add_edge(bill_nid, nid, "POSTED_AS")

    # ── Payments ──────────────────────────────────────────────────────────────
    for r in conn.execute("SELECT * FROM payments"):
        nid = f"PAY_{r['accountingDocument']}_{r['accountingDocumentItem']}"
        add_node(nid, "Payment", f"PAY-{r['accountingDocument']}", {
            "accountingDocument": r["accountingDocument"],
            "amount": r["amountInTransactionCurrency"],
            "currency": r["transactionCurrency"],
            "postingDate": r["postingDate"],
            "customer": r["customer"],
            "clearingDate": r["clearingDate"],
        })
        cust_nid = f"CUST_{r['customer']}"
        add_edge(cust_nid, nid, "MADE_PAYMENT")

    conn.close()

    return {
        "nodes": [{"data": n} for n in nodes.values()],
        "edges": [{"data": {**e, "id": f"e{i}"}} for i, e in enumerate(edges)],
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "by_type": {
                t: sum(1 for n in nodes.values() if n["type"] == t)
                for t in NODE_META
            }
        }
    }


def detect_broken_flows() -> list[dict]:
    """
    Returns orders with incomplete O2C flows.
    A broken flow = delivered (status C) but billing status is empty.
    This is a pre-computed insight surfaced in the UI dashboard panel.
    """
    conn = _conn()
    rows = conn.execute("""
        SELECT
            soh.salesOrder,
            soh.soldToParty,
            bp.businessPartnerFullName AS customerName,
            soh.totalNetAmount,
            soh.transactionCurrency,
            soh.overallDeliveryStatus,
            soh.overallOrdReltdBillgStatus,
            soh.creationDate
        FROM sales_order_headers soh
        LEFT JOIN business_partners bp ON bp.customer = soh.soldToParty
        WHERE soh.overallDeliveryStatus = 'C'
          AND (soh.overallOrdReltdBillgStatus = ''
               OR soh.overallOrdReltdBillgStatus IS NULL)
        ORDER BY soh.totalNetAmount DESC
        LIMIT 20
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
