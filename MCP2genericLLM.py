# MCP2genericLLM.py 
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
DEFAULT_OPENAI_COMPAT_URL = "http://127.0.0.1:8000/v1/chat/completions"  # placeholder

DEFAULT_MODEL = "llama3.1:8b"
TIMEOUT_S = 60
MAX_STEPS = 8


# ----------------------------
# MCP CLIENT (HTTP JSON-RPC)
# ----------------------------
class MCP:
    def __init__(self, url: str):
        self.url = url
        self._id = 0

    def rpc(self, method: str, params: Optional[dict] = None) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        r = requests.post(self.url, json=payload, timeout=TIMEOUT_S)
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise RuntimeError(j["error"])
        return j

    def initialize(self) -> None:
        try:
            self.rpc("initialize", {})
            self.rpc("notifications/initialized", {})
        except Exception:
            pass

    def tools_call(self, name: str, arguments: dict) -> dict:
        return self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]

    def resources_read(self, uri: str) -> dict:
        return self.rpc("resources/read", {"uri": uri})["result"]


# ----------------------------
# LLM CLIENTS
# ----------------------------
class LLM:
    def chat(self, model: str, messages: List[dict], tools: List[dict]) -> dict:
        raise NotImplementedError


class OllamaLLM(LLM):
    def __init__(self, url: str):
        self.url = url

    def chat(self, model: str, messages: List[dict], tools: List[dict]) -> dict:
        payload = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}
        r = requests.post(self.url, json=payload, timeout=TIMEOUT_S)
        r.raise_for_status()
        return r.json()


class OpenAICompatLLM(LLM):
    def __init__(self, url: str, api_key: Optional[str] = None):
        self.url = url
        self.api_key = api_key

    def chat(self, model: str, messages: List[dict], tools: List[dict]) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}
        r = requests.post(self.url, headers=headers, json=payload, timeout=TIMEOUT_S)
        r.raise_for_status()
        return r.json()


# ----------------------------
# TOOL BRIDGE (MCP <-> LLM tools)
# ----------------------------
@dataclass
class ToolMapEntry:
    llm_tool_name: str
    mcp_kind: str
    mcp_params_builder: Any  # callable(args)->(kind, params)


def build_default_tools_for_sm_mcp() -> Tuple[List[dict], Dict[str, ToolMapEntry]]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "sm_save",
                "description": "Save symbolic memory entry to SM-MCP",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "text": {"type": "string"},
                        "cat": {"type": "string"},
                        "subcat": {"type": "string"},
                        "aliases": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["symbol", "text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sm_get",
                "description": "Fetch symbolic memory entry from SM-MCP",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            },
        },
    ]

    def _save_builder(args: dict):
        return ("tools_call", {"name": "sm.texts.save", "arguments": args})

    def _get_builder(args: dict):
        sym = args["symbol"]
        return ("resources_read", {"uri": f"resource://sm/v1/texts/{sym}"})

    mapping = {
        "sm_save": ToolMapEntry("sm_save", "tools_call", _save_builder),
        "sm_get": ToolMapEntry("sm_get", "resources_read", _get_builder),
    }
    return tools, mapping


def exec_tool_call(mcp: MCP, mapping: Dict[str, ToolMapEntry], tool_call: dict) -> Tuple[str, str, dict]:
    fn = tool_call["function"]
    name = fn["name"]
    args = json.loads(fn.get("arguments") or "{}")

    if name not in mapping:
        return (tool_call.get("id") or "", name, {"error": f"unknown tool: {name}"})

    entry = mapping[name]
    kind, params = entry.mcp_params_builder(args)

    if kind == "tools_call":
        res = mcp.tools_call(params["name"], params["arguments"])
    elif kind == "resources_read":
        res = mcp.resources_read(params["uri"])
    else:
        res = {"error": f"unsupported mcp dispatch: {kind}"}

    return (tool_call.get("id") or "", name, res)


def extract_text_from_resources_read(result: dict) -> Optional[str]:
    # SM-MCP resources/read => {"contents":[{"type":"text","text":"..."}]}
    contents = result.get("contents") or []
    if not contents:
        return None
    return contents[0].get("text")


# ----------------------------
# TOOL LOOP RUNNER
# ----------------------------
def run_loop(llm: LLM, mcp: MCP, model: str, user_prompt: str, strict_get: bool) -> None:
    tools, mapping = build_default_tools_for_sm_mcp()
    mcp.initialize()

    messages: List[dict] = [{"role": "user", "content": user_prompt}]

    for _ in range(MAX_STEPS):
        resp = llm.chat(model=model, messages=messages, tools=tools)
        msg = resp["choices"][0]["message"]

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            print(msg.get("content", ""))
            return

        messages.append(msg)

        for tc in tool_calls:
            tc_id, tool_name, result = exec_tool_call(mcp, mapping, tc)

            # STRICT-GET: if sm_get happened, print ONLY stored text and exit
            if strict_get and tool_name == "sm_get":
                txt = extract_text_from_resources_read(result)
                if txt is None:
                    raise RuntimeError("strict-get: sm_get returned no text")
                print(txt)
                return

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": tool_name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    raise RuntimeError("Tool loop exceeded MAX_STEPS")


# ----------------------------
# CLI
# ----------------------------
def main():
    ap = argparse.ArgumentParser(prog="MCP2genericLLM", description="MCP → generic tool-calling LLM bridge (MVP)")
    ap.add_argument("--backend", choices=["ollama", "openai_compat"], default="ollama")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    ap.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    ap.add_argument("--openai-url", default=DEFAULT_OPENAI_COMPAT_URL)
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY") or os.environ.get("MISTRAL_API_KEY"))
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--strict-get", action="store_true", help="If sm_get is called, print ONLY retrieved text and exit.")

    args = ap.parse_args()

    mcp = MCP(args.mcp_url)

    if args.backend == "ollama":
        llm = OllamaLLM(args.ollama_url)
    else:
        llm = OpenAICompatLLM(args.openai_url, api_key=args.api_key)

    run_loop(llm=llm, mcp=mcp, model=args.model, user_prompt=args.prompt, strict_get=args.strict_get)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
