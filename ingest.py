"""
Ingest all JSONL files into SQLite.
Design decisions:
- SQLite with WAL mode: handles concurrent reads perfectly, zero infrastructure
- LLMs generate SQL far more reliably than Cypher/Gremlin; this is the right call
- Flatten nested JSON objects (creationTime.hours etc.) to plain strings
- Index every FK column used in JOINs: mandatory for sub-100ms query latency
"""
import sqlite3, json, pathlib, re

DATA_DIR = pathlib.Path(
    pathlib.Path(__file__).parent / "dataset" / "sap-o2c-data"
    if (pathlib.Path(__file__).parent / "dataset").exists()
    else pathlib.Path("/home/claude/dataset/sap-o2c-data")
)
DB_PATH  = pathlib.Path(__file__).parent / "data.db"

# Map folder name -> table name (rename for clarity)
TABLE_MAP = {
    "sales_order_headers":                     "sales_order_headers",
    "sales_order_items":                       "sales_order_items",
    "outbound_delivery_headers":               "outbound_delivery_headers",
    "billing_document_cancellations":          "billing_documents",
    "journal_entry_items_accounts_receivable": "journal_entries",
    "payments_accounts_receivable":            "payments",
    "business_partners":                       "business_partners",
    "customer_company_assignments":            "customer_company",
    "customer_sales_area_assignments":         "customer_sales_area",
    "plants":                                  "plants",
    "product_descriptions":                    "product_descriptions",
    "product_plants":                          "product_plants",
    "product_storage_locations":               "product_storage_locations",
}

def flatten(obj, prefix=""):
    out = {}
    for k, v in obj.items():
        key = prefix + k
        if isinstance(v, dict):
            out.update(flatten(v, key + "_"))
        elif isinstance(v, list):
            out[key] = json.dumps(v)
        elif v is None:
            out[key] = None
        else:
            out[key] = str(v)
    return out

def safe_col(name):
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)

def load_table(conn, folder_name, table_name):
    folder = DATA_DIR / folder_name
    if not folder.exists():
        print(f"  WARNING: {folder} not found, skipping")
        return 0
    rows = []
    for f in sorted(folder.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(flatten(json.loads(line)))
                except Exception:
                    pass
    if not rows:
        return 0

    # Union of all columns across every row (handles schema variation between parts)
    all_cols_ordered = []
    seen = set()
    for r in rows:
        for k in r:
            ck = safe_col(k)
            if ck not in seen:
                seen.add(ck)
                all_cols_ordered.append(ck)
    cols = all_cols_ordered

    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
    conn.execute(f'CREATE TABLE {table_name} ({col_defs})')

    placeholders = ", ".join("?" for _ in cols)
    for r in rows:
        # Map original camelCase key -> safe_col version
        mapped = {safe_col(k): v for k, v in r.items()}
        vals = [mapped.get(c) for c in cols]
        conn.execute(f'INSERT INTO {table_name} VALUES ({placeholders})', vals)
    return len(rows)

def create_indexes(conn):
    indexes = [
        ("sales_order_headers",  "salesOrder"),
        ("sales_order_headers",  "soldToParty"),
        ("sales_order_items",    "salesOrder"),
        ("sales_order_items",    "material"),
        ("billing_documents",    "soldToParty"),
        ("billing_documents",    "accountingDocument"),
        ("billing_documents",    "billingDocument"),
        ("journal_entries",      "referenceDocument"),
        ("journal_entries",      "customer"),
        ("journal_entries",      "accountingDocument"),
        ("payments",             "customer"),
        ("payments",             "clearingAccountingDocument"),
        ("business_partners",    "customer"),
        ("product_descriptions", "product"),
        ("outbound_delivery_headers", "deliveryDocument"),
    ]
    for table, col in indexes:
        try:
            conn.execute(
                f'CREATE INDEX IF NOT EXISTS "idx_{table}_{col}" ON {table} ("{col}")'
            )
        except Exception as e:
            print(f"  Index warning {table}.{col}: {e}")

def run():
    print("Building database from JSONL files...")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=20000")

    total = 0
    for folder, table in TABLE_MAP.items():
        n = load_table(conn, folder, table)
        total += n
        if n:
            print(f"  {table}: {n} rows")

    create_indexes(conn)
    conn.commit()
    conn.close()
    print(f"\nDone — {total} total rows, DB at {DB_PATH}")

if __name__ == "__main__":
    run()
