# SymbolicMemoryMCP

**Explicit, deterministic symbolic memory for AI systems via MCP (Model
Context Protocol).**

SymbolicMemoryMCP makes AI memory explicit: knowledge is stored by
stable symbolic keys instead of hidden token state.

------------------------------------------------------------------------

## 🚀 Why This Matters

Most LLM workflows rely on implicit, probabilistic memory --- prompt
windows, vector stores, heuristics.

SymbolicMemoryMCP provides:

-   Deterministic recall\
-   Stable symbolic addressing\
-   Alias support\
-   Structured taxonomy\
-   MCP protocol interface\
-   AI‑agnostic integration

------------------------------------------------------------------------

## 🧠 Core Concept

Store knowledge explicitly:

    HGI.DEF → "Hybrid General Intelligence = AI + human symbiosis"

Retrieve deterministically:

    sm_get("HGI.DEF")

------------------------------------------------------------------------

## ⚡ Quick Start

### Install

    pip install fastapi uvicorn pydantic requests

### Run Server

    uvicorn server:app --host 127.0.0.1 --port 8000

Endpoint:

    http://127.0.0.1:8000/mcp

------------------------------------------------------------------------

## 🧪 Smoke Test --- MCP

Save:

    symbol: TEST.SMOKE
    text: smoke ok

Retrieve:

    smoke ok

------------------------------------------------------------------------

## 🤖 Smoke Test --- With LLM Bridge

    python MCP2genericLLM.py --strict-get ...

Expected:

    bridge ok

------------------------------------------------------------------------

## 🏗 Architecture

    LLM → Bridge → MCP → Symbolic Memory Store

------------------------------------------------------------------------

## 💼 License

BUSL --- Free for private use, paid for business use, converts to open
source after 3 years.

------------------------------------------------------------------------

## Author

Aki Hirvilammi
