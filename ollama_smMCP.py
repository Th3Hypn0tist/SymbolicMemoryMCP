import json
import requests

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"  # Ollama OpenAI-compatible
MCP_URL    = "http://127.0.0.1:8000/mcp"                   # your SM-MCP server

MODEL = "llama3.1:8b"  # or whatever you run in Ollama


def mcp_call(method: str, params: dict):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = requests.post(MCP_URL, json=payload, timeout=20)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


TOOLS = [
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


def ollama_chat(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def run():
    # Optional: MCP initialize handshake (safe even if client doesn't require it)
    try:
        mcp_call("initialize", {})
        mcp_call("notifications/initialized", {})
    except Exception:
        pass

    messages = [
        {
            "role": "user",
            "content": (
                "Save this into symbolic memory and then retrieve it.\n"
                "symbol=HGI.DEF\n"
                "cat=ai\n"
                "subcat=architecture.hybrid\n"
                "text=HGI = AI:n ja ihmisen symbioosi."
            ),
        }
    ]

    # Tool-calling loop (max 5 steps)
    for _ in range(5):
        resp = ollama_chat(messages)
        msg = resp["choices"][0]["message"]

        # If model returns tool calls
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            print(msg.get("content", ""))
            return

        # Append assistant message with tool_calls
        messages.append(msg)

        # Execute each tool call and append tool results
        for tc in tool_calls:
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"] or "{}")

            if name == "sm_save":
                result = mcp_call(
                    "tools/call",
                    {"name": "sm.texts.save", "arguments": args},
                )
            elif name == "sm_get":
                result = mcp_call(
                    "resources/read",
                    {"uri": f"resource://sm/v1/texts/{args['symbol']}"},
                )
            else:
                result = {"error": f"unknown tool: {name}"}

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    raise RuntimeError("Tool loop exceeded max steps")


if __name__ == "__main__":
    run()
