#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

import requests


DEFAULT_URL = "http://127.0.0.1:8000/mcp"
TIMEOUT_S = 10
LAST_APPLY_FILE = ".sm_last_apply.json"

MIN_SCORE = 0.65  # default accept threshold


# ----------------------------
# MCP HTTP JSON-RPC
# ----------------------------
class MCPClient:
    def __init__(self, url: str):
        self.url = url
        self._id = 0

    def rpc(self, method: str, params: Optional[dict] = None) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        r = requests.post(self.url, json=payload, timeout=TIMEOUT_S)
        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text}") from None
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {data}")
        if "error" in data:
            raise RuntimeError(f"JSON-RPC error: {data['error']}")
        return data

    def initialize(self) -> dict:
        init = self.rpc("initialize", {})
        self.rpc("notifications/initialized", {})
        return init

    def tools_call(self, name: str, arguments: dict) -> dict:
        return self.rpc("tools/call", {"name": name, "arguments": arguments})

    def resources_read(self, uri: str) -> dict:
        return self.rpc("resources/read", {"uri": uri})


# ----------------------------
# DEFINE BLOCK PARSER (v1.2)
# ----------------------------
@dataclass
class DefineBlock:
    symbol: Optional[str]
    project: str
    cat: Optional[str]
    subcat: Optional[str]
    tags: List[str]
    aliases: List[str]
    body: str


_DEFINE_RE = re.compile(r"```DEFINE\s*\n(.*?)\n```", re.DOTALL)


def _parse_kv_headers(text: str) -> Tuple[Dict[str, str], str]:
    lines = text.splitlines()
    headers: Dict[str, str] = {}
    body_lines: List[str] = []

    in_headers = True
    for i, line in enumerate(lines):
        if in_headers:
            if line.strip() == "":
                in_headers = False
                body_lines = lines[i + 1 :]
                break
            m = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
            if not m:
                in_headers = False
                body_lines = lines[i:]
                break
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            headers[key] = val
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).rstrip("\n")
    return headers, body


def parse_last_define_block(md_text: str) -> DefineBlock:
    blocks = _DEFINE_RE.findall(md_text)
    if not blocks:
        raise ValueError("No ```DEFINE ...``` block found.")

    raw = blocks[-1]
    headers, body = _parse_kv_headers(raw)

    symbol = headers.get("symbol") or None
    project = headers.get("project") or "default"
    cat = headers.get("cat") or None
    subcat = headers.get("subcat") or None

    tags_raw = headers.get("tags") or ""
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    aliases_raw = headers.get("aliases") or ""
    aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]

    if not body.strip():
        raise ValueError("DEFINE block body is empty.")

    return DefineBlock(
        symbol=symbol,
        project=project,
        cat=cat,
        subcat=subcat,
        tags=tags,
        aliases=aliases,
        body=body,
    )


# ----------------------------
# TAXONOMY SUGGESTION UX
# ----------------------------
def _pick_top_suggestion(suggestions: dict) -> Tuple[Optional[str], Optional[str], float]:
    """
    Returns (cat, subcat, score) where score is min(cat_score, subcat_score) if both present.
    Subcat suggestions include cat binding; we prefer a matching pair.
    """
    cat_sug = suggestions.get("cat") or []
    sub_sug = suggestions.get("subcat") or []

    top_cat = cat_sug[0]["value"] if cat_sug else None
    top_cat_score = float(cat_sug[0]["score"]) if cat_sug else 0.0

    # Prefer subcat whose cat matches top_cat; else take first
    chosen_sub = None
    chosen_sub_score = 0.0
    if sub_sug:
        for s in sub_sug:
            if top_cat and s.get("cat") == top_cat:
                chosen_sub = s["value"]
                chosen_sub_score = float(s["score"])
                break
        if chosen_sub is None:
            chosen_sub = sub_sug[0]["value"]
            chosen_sub_score = float(sub_sug[0]["score"])
            # if this subcat has an associated cat, use it
            if sub_sug[0].get("cat"):
                top_cat = sub_sug[0]["cat"]
                top_cat_score = top_cat_score or float(sub_sug[0]["score"])

    score = min(top_cat_score or 0.0, chosen_sub_score or 0.0) if (top_cat and chosen_sub) else (top_cat_score or chosen_sub_score)
    return top_cat, chosen_sub, score


def _prompt_apply(cat: Optional[str], subcat: Optional[str], score: float) -> str:
    default_yes = score >= MIN_SCORE
    default = "Y" if default_yes else "n"
    prompt = f"Apply suggested taxonomy cat={cat!r} subcat={subcat!r} (score={score:.2f})? [Y/n/e/u] (default {default}): "
    ans = input(prompt).strip()
    if not ans:
        return default
    return ans


def _prompt_edit(cat: Optional[str], subcat: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    new_cat = input(f"cat [{cat or ''}]: ").strip() or (cat or None)
    new_sub = input(f"subcat [{subcat or ''}]: ").strip() or (subcat or None)
    return new_cat, new_sub


def _load_last_apply() -> Optional[dict]:
    if not os.path.exists(LAST_APPLY_FILE):
        return None
    try:
        with open(LAST_APPLY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_last_apply(data: dict) -> None:
    with open(LAST_APPLY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ----------------------------
# COMMANDS
# ----------------------------
def cmd_init(args: argparse.Namespace) -> None:
    cli = MCPClient(args.url)
    resp = cli.initialize()
    print(resp)


def cmd_save(args: argparse.Namespace) -> None:
    md = open(args.file, "r", encoding="utf-8").read()
    blk = parse_last_define_block(md)

    symbol = args.symbol or blk.symbol
    if not symbol:
        raise SystemExit("Error: symbol missing. Provide 'symbol:' in DEFINE or pass it as argument.")

    cli = MCPClient(args.url)
    cli.initialize()

    payload = {
        "symbol": symbol,
        "text": blk.body,
        "cat": blk.cat,
        "subcat": blk.subcat,
        "aliases": blk.aliases,
    }

    resp = cli.tools_call("sm.texts.save", payload)
    result = resp.get("result", {})
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # If missing taxonomy, and server returned suggestions -> prompt to apply
    suggestions = result.get("suggestions")
    already_has = (blk.cat is not None and blk.subcat is not None)
    if suggestions and not already_has:
        sug_cat, sug_sub, score = _pick_top_suggestion(suggestions)
        if not sug_cat and not sug_sub:
            return

        ans = _prompt_apply(sug_cat, sug_sub, score).lower()

        if ans == "u":
            last = _load_last_apply()
            if not last:
                print("Nothing to undo.")
                return
            # rollback to previous meta
            rb_payload = {
                "symbol": last["symbol"],
                "text": blk.body,  # keep text; taxonomy rollback only
                "cat": last.get("prev_cat"),
                "subcat": last.get("prev_subcat"),
                "aliases": blk.aliases,
            }
            rb = cli.tools_call("sm.texts.save", rb_payload)
            print("UNDO:", json.dumps(rb.get("result", {}), ensure_ascii=False, indent=2))
            return

        if ans == "e":
            sug_cat, sug_sub = _prompt_edit(sug_cat, sug_sub)
            ans = "y"

        if ans == "y":
            prev = result.get("prev", {}) or {}
            apply_payload = {
                "symbol": symbol,
                "text": blk.body,
                "cat": sug_cat,
                "subcat": sug_sub,
                "aliases": blk.aliases,
            }
            applied = cli.tools_call("sm.texts.save", apply_payload)
            applied_res = applied.get("result", {})
            print("APPLIED:", json.dumps(applied_res, ensure_ascii=False, indent=2))

            _save_last_apply({
                "symbol": symbol,
                "prev_cat": prev.get("cat"),
                "prev_subcat": prev.get("subcat"),
                "new_cat": sug_cat,
                "new_subcat": sug_sub,
                "score": score,
            })
            return

        # n / anything else => do nothing
        return


def cmd_get(args: argparse.Namespace) -> None:
    cli = MCPClient(args.url)
    cli.initialize()
    uri = f"resource://sm/v1/texts/{args.symbol}"
    resp = cli.resources_read(uri)
    try:
        contents = resp["result"]["contents"]
        txt = contents[0].get("text", "") if contents else ""
        print(txt)
    except Exception:
        print(resp)


def main() -> None:
    p = argparse.ArgumentParser(prog="client", description="Minimal SM-MCP client (DEFINE-aware) over HTTP JSON-RPC")
    p.add_argument("--url", default=DEFAULT_URL, help=f"MCP endpoint URL (default: {DEFAULT_URL})")

    sp = p.add_subparsers(dest="cmd", required=True)

    pi = sp.add_parser("init", help="Run MCP initialize handshake")
    pi.set_defaults(func=cmd_init)

    ps = sp.add_parser("save", help="Save last DEFINE block from a markdown file")
    ps.add_argument("file", help="Markdown file containing ```DEFINE block")
    ps.add_argument("symbol", nargs="?", help="Optional symbol override")
    ps.set_defaults(func=cmd_save)

    pg = sp.add_parser("get", help="Get text by symbol (server may resolve aliases)")
    pg.add_argument("symbol")
    pg.set_defaults(func=cmd_get)

    args = p.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
