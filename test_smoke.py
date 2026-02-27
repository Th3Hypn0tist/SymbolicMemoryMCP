#!/usr/bin/env python3
import json
import sys
import requests

MCP_URL = "http://127.0.0.1:8000/mcp"

def rpc(method, params=None, id_=1):
    payload = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    r = requests.post(MCP_URL, json=payload, timeout=10)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]

def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)

def main():
    # 1) handshake
    init = rpc("initialize", {}, 1)
    assert_true("protocolVersion" in init, "initialize: missing protocolVersion")
    rpc("notifications/initialized", {}, 2)

    # 2) save with taxonomy + aliases
    save1 = rpc("tools/call", {
        "name": "sm.texts.save",
        "arguments": {
            "symbol": "TST.ONE",
            "text": "hello world one",
            "cat": "test",
            "subcat": "smoke.basic",
            "aliases": ["one", "first"]
        }
    }, 3)
    assert_true(save1["symbol"] == "TST.ONE", "save1: wrong symbol")

    # 3) read by symbol
    read1 = rpc("resources/read", {"uri": "resource://sm/v1/texts/TST.ONE"}, 4)
    txt1 = read1["contents"][0]["text"]
    assert_true(txt1 == "hello world one", "read1: wrong text")

    # 4) read by alias
    read2 = rpc("resources/read", {"uri": "resource://sm/v1/texts/one"}, 5)
    txt2 = read2["contents"][0]["text"]
    assert_true(txt2 == "hello world one", "read2: alias resolve failed")

    # 5) create baseline taxonomy neighbor
    rpc("tools/call", {
        "name": "sm.texts.save",
        "arguments": {
            "symbol": "TST.NEIGHBOR",
            "text": "hybrid intelligence symbolic memory",
            "cat": "ai",
            "subcat": "architecture.hybrid"
        }
    }, 6)

    # 6) save WITHOUT cat/subcat -> expect suggestions
    save2 = rpc("tools/call", {
        "name": "sm.texts.save",
        "arguments": {
            "symbol": "TST.TWO",
            "text": "hybrid intelligence and symbolic memory"
        }
    }, 7)
    sugg = save2.get("suggestions")
    assert_true(sugg is not None, "save2: expected suggestions when cat/subcat missing")
    assert_true(len(sugg.get("cat", [])) > 0, "save2: suggestions.cat empty")
    # subcat suggestions may be empty if no strong match; cat should exist
    print("suggestions:", json.dumps(sugg, ensure_ascii=False, indent=2))

    print("OK: smoke tests passed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL:", e)
        sys.exit(1)
