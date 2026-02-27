from __future__ import annotations

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
import sqlite3
import hashlib
import datetime
import re
from typing import Optional, List, Dict, Tuple

app = FastAPI()

DB_PATH = "sm.db"
PROTOCOL_VERSION = "2025-06-18"


# ----------------------------
# DB INIT
# ----------------------------
def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS texts (
        symbol TEXT PRIMARY KEY,
        body TEXT NOT NULL,
        cat TEXT NULL,
        subcat TEXT NULL,
        hash TEXT NOT NULL,
        ts_created TEXT NOT NULL,
        ts_updated TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS aliases (
        alias TEXT PRIMARY KEY,
        symbol TEXT NOT NULL
    )
    """)

    # indexes for scale
    c.execute("CREATE INDEX IF NOT EXISTS idx_texts_cat_sub ON texts(cat, subcat)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_alias_symbol ON aliases(symbol)")

    conn.commit()
    conn.close()


init_db()


# ----------------------------
# MODELS
# ----------------------------
class SaveArgs(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=128)
    text: str = Field(..., min_length=1)
    cat: Optional[str] = Field(default=None, max_length=64)
    subcat: Optional[str] = Field(default=None, max_length=128)  # dot-path
    aliases: Optional[List[str]] = Field(default=None)


# ----------------------------
# HELPERS
# ----------------------------
def now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def tokenize(text: str, max_tokens: int = 80) -> List[str]:
    # deterministic, lightweight
    toks = _TOKEN_RE.findall(text.lower())
    # de-dup while preserving order
    seen = set()
    out = []
    for t in toks:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= max_tokens:
            break
    return out


def jaccard(a: List[str], b: List[str]) -> float:
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def resolve_symbol(sym: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT symbol FROM texts WHERE symbol=?", (sym,))
    row = c.fetchone()
    if row:
        conn.close()
        return sym

    c.execute("SELECT symbol FROM aliases WHERE alias=?", (sym,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_existing_meta(symbol: str) -> Tuple[Optional[str], Optional[str]]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT cat, subcat FROM texts WHERE symbol=?", (symbol,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None, None
    return row[0], row[1]


def save_text(args: SaveArgs) -> Dict[str, object]:
    ts = now_iso()
    h = sha256_text(args.text)

    prev_cat, prev_subcat = get_existing_meta(args.symbol)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # detect first create
    c.execute("SELECT 1 FROM texts WHERE symbol=?", (args.symbol,))
    existed = c.fetchone() is not None

    if existed:
        c.execute("""
        UPDATE texts
           SET body=?,
               cat=?,
               subcat=?,
               hash=?,
               ts_updated=?
         WHERE symbol=?
        """, (args.text, args.cat, args.subcat, h, ts, args.symbol))
        ts_created = None
        c.execute("SELECT ts_created FROM texts WHERE symbol=?", (args.symbol,))
        row = c.fetchone()
        ts_created = row[0] if row else ts
    else:
        c.execute("""
        INSERT INTO texts(symbol, body, cat, subcat, hash, ts_created, ts_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (args.symbol, args.text, args.cat, args.subcat, h, ts, ts))
        ts_created = ts

    if args.aliases:
        for a in args.aliases:
            a = a.strip()
            if not a:
                continue
            c.execute("INSERT OR REPLACE INTO aliases(alias, symbol) VALUES (?, ?)", (a, args.symbol))

    conn.commit()
    conn.close()

    return {
        "status": "created" if not existed else "updated",
        "symbol": args.symbol,
        "hash": h,
        "ts_created": ts_created,
        "ts_updated": ts,
        "prev": {"cat": prev_cat, "subcat": prev_subcat},
    }


def suggest_taxonomy(symbol: str, text: str, limit_rows: int = 2000, min_sim: float = 0.10) -> Dict[str, object] | None:
    """
    Deterministic, no-LLM suggestion:
    - compute token set for new text
    - scan up to limit_rows existing rows
    - aggregate similarity weights by cat and subcat (only those that exist)
    """
    new_toks = tokenize(f"{symbol} {text}", max_tokens=80)
    if not new_toks:
        return None

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
      SELECT symbol, body, cat, subcat
        FROM texts
       WHERE cat IS NOT NULL OR subcat IS NOT NULL
       LIMIT ?
    """, (limit_rows,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return None

    cat_scores: Dict[str, float] = {}
    subcat_scores: Dict[str, float] = {}
    neighbors: List[Tuple[str, float]] = []

    for sym, body, cat, subcat in rows:
        # short-circuit: if no taxonomy, skip
        if not cat and not subcat:
            continue
        toks = tokenize(f"{sym} {body}", max_tokens=80)
        sim = jaccard(new_toks, toks)
        if sim < min_sim:
            continue
        neighbors.append((sym, sim))
        if cat:
            cat_scores[cat] = cat_scores.get(cat, 0.0) + sim
        if cat and subcat:
            key = f"{cat}::{subcat}"
            subcat_scores[key] = subcat_scores.get(key, 0.0) + sim

    if not cat_scores and not subcat_scores:
        return None

    neighbors.sort(key=lambda x: x[1], reverse=True)
    neighbors = neighbors[:5]

    def top_n(d: Dict[str, float], n: int = 3) -> List[Dict[str, object]]:
        items = sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]
        total = sum(d.values()) or 1.0
        out = []
        for k, v in items:
            out.append({"value": k, "score": round(v / total, 4)})
        return out

    cats = top_n(cat_scores, 3)

    subcats = []
    if subcat_scores:
        # convert to cat/subcat outputs with normalized score
        items = sorted(subcat_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
        total = sum(subcat_scores.values()) or 1.0
        for k, v in items:
            cat, subcat = k.split("::", 1)
            subcats.append({"cat": cat, "value": subcat, "score": round(v / total, 4)})

    return {
        "cat": cats,
        "subcat": subcats,
        "neighbors": [{"symbol": s, "sim": round(sim, 4)} for s, sim in neighbors],
    }


# ----------------------------
# MCP ENDPOINT (single POST /mcp)
# ----------------------------
@app.post("/mcp")
async def mcp(request: Request):
    data = await request.json()

    method = data.get("method")
    params = data.get("params", {}) or {}
    id_ = data.get("id")

    # --- MCP INITIALIZE HANDSHAKE ---
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": id_,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": "sm-mcp", "version": "0.1"},
                "capabilities": {
                    "resources": {},
                    "tools": {},
                },
            },
        }

    if method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": id_, "result": None}

    # --- TOOL: save text ---
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "sm.texts.save":
            parsed = SaveArgs(**args)

            # do the save
            result = save_text(parsed)

            # suggestion logic (hint-only)
            suggestions = None
            if parsed.cat is None or parsed.subcat is None:
                suggestions = suggest_taxonomy(parsed.symbol, parsed.text)

            if suggestions:
                result["suggestions"] = suggestions

            return {"jsonrpc": "2.0", "id": id_, "result": result}

    # --- RESOURCE READ ---
    if method == "resources/read":
        uri = params.get("uri")
        if not isinstance(uri, str) or "://" not in uri:
            raise HTTPException(400, "Invalid uri")

        # Our client uses: resource://sm/v1/texts/<symbol>
        symbol = uri.split("/")[-1]
        resolved = resolve_symbol(symbol)
        if not resolved:
            raise HTTPException(404, "Not found")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT body FROM texts WHERE symbol=?", (resolved,))
        row = c.fetchone()
        conn.close()

        if not row:
            raise HTTPException(404, "Not found")

        body = row[0]
        return {
            "jsonrpc": "2.0",
            "id": id_,
            "result": {
                "contents": [
                    {"uri": uri, "type": "text", "text": body}
                ]
            },
        }

    raise HTTPException(400, f"Unknown method: {method}")
