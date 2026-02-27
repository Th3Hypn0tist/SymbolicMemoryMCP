# SymbolicMemoryMCP

**Explicit, deterministic symbolic memory for AI systems via MCP (Model
Context Protocol).**

SymbolicMemoryMCP provides a simple, reliable way for AI tools and
agents to store and retrieve knowledge using stable symbols instead of
hidden chat history or probabilistic recall.

------------------------------------------------------------------------

## ✨ Core Idea

Instead of "AI memory" being implicit and unreliable, this system makes
it:

-   Explicit
-   Deterministic
-   Persistent
-   AI‑agnostic
-   Structured
-   Alias‑aware

------------------------------------------------------------------------

## ⚡ Quick Start

### Start MCP Server

    uvicorn server:app --host 127.0.0.1 --port 8000

------------------------------------------------------------------------

## 🧪 Smoke Test --- MCP Only

Save:

    symbol = TEST.SMOKE
    text = smoke ok

Retrieve:

    smoke ok

------------------------------------------------------------------------

## 🤖 Smoke Test --- With LLM Bridge

    python MCP2genericLLM.py --strict-get ...

Expected:

    bridge ok

------------------------------------------------------------------------

## 💼 License

BUSL --- Free for private use, paid for business use, converts to open
source after 3 years.

------------------------------------------------------------------------

## Author

Aki Hirvilammi
