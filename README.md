# SymbolicMemoryMCP

Explicit, deterministic symbolic memory for AI systems via MCP (Model
Context Protocol).

SymbolicMemoryMCP provides a small, focused MCP server that allows LLMs
and agents to store and retrieve curated knowledge by stable symbolic
keys instead of relying on probabilistic recall.

Repository contents:

-   server.py --- FastAPI-based MCP JSON-RPC server
-   client.py --- CLI client for manual save/get workflows
-   tests_smoke.py --- end-to-end MCP smoke tests
-   MCP2genericLLM.py --- reference LLM bridge (tested with Ollama)
-   LICENSE.md --- Business Source License (BUSL 1.1)

------------------------------------------------------------------------

CORE IDEA

SYMBOL → Deterministic resolution → Text payload

Example:

HGI.DEF → "Hybrid General Intelligence = AI + human symbiosis"

An LLM retrieves this using sm_get instead of re-inventing definitions.

------------------------------------------------------------------------

IMPLEMENTED MCP SURFACE (v0.1.0)

Save MCP method: tools/call Tool name: sm.texts.save

Arguments example:

{ "symbol": "HGI.DEF", "text": "Hybrid General Intelligence = AI + human
symbiosis", "cat": "ai", "subcat": "concepts.intelligence", "aliases":
\["hgi", "hybrid intelligence"\] }

Retrieve MCP method: resources/read

URI: resource://sm/v1/texts/`<symbol_or_alias>`{=html}

------------------------------------------------------------------------

INSTALLATION

pip install fastapi uvicorn pydantic requests

------------------------------------------------------------------------

RUN SERVER

uvicorn server:app --host 127.0.0.1 --port 8000

Endpoint: http://127.0.0.1:8000/mcp

------------------------------------------------------------------------

MCP SMOKE TEST

python tests_smoke.py

Expected: OK: smoke tests passed

------------------------------------------------------------------------

CLI EXAMPLES

Save:

python client.py save --symbol HGI.DEF --text "Hybrid General
Intelligence = AI + human symbiosis" --cat ai --subcat
concepts.intelligence --aliases hgi "hybrid intelligence"

Get:

python client.py get --symbol HGI.DEF

------------------------------------------------------------------------

LLM BRIDGE (OLLAMA)

uvicorn server:app --port 8000 ollama serve

python MCP2genericLLM.py --backend ollama --model llama3.1:8b --mcp-url
http://127.0.0.1:8000/mcp --ollama-url
http://127.0.0.1:11434/v1/chat/completions --strict-get --prompt "You
MUST use tools. Save symbol TEST.BRIDGE with text 'bridge ok'. Then call
sm_get using symbol TEST.BRIDGE."

Expected: bridge ok

------------------------------------------------------------------------

HOW LLMs SHOULD USE THIS

Call sm_get when: - A canonical definition is required - A
policy/invariant constrains output

Call sm_save when: - A stable definition or invariant must persist

Prompt template:

You MUST use tools. Resolve important terms via sm_get before answering.
If missing, propose a symbol and store it via sm_save. Base final answer
strictly on retrieved ground truth.

------------------------------------------------------------------------

STORAGE

-   SQLite backend
-   Single-process transactional safety
-   No distributed guarantees

------------------------------------------------------------------------

ROADMAP (NOT IMPLEMENTED)

-   Prefix search
-   Versioning
-   Alias management endpoints
-   JSON-schema payloads
-   Batch ops

------------------------------------------------------------------------

LICENSE

Business Source License 1.1 (BUSL 1.1)

-   Free for personal use
-   Commercial use requires paid license
-   Converts to open source after 3 years

See LICENSE.md.

------------------------------------------------------------------------

Author: Aki Hirvilammi
