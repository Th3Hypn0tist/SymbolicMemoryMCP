# SymbolicMemoryMCP

[![License: BUSL-1.1](https://img.shields.io/badge/license-BUSL--1.1-blue)](LICENSE.md)
[![MCP](https://img.shields.io/badge/protocol-MCP-brightgreen)](#implemented-mcp-surface-v010)
[![Python](https://img.shields.io/badge/python-3.10%2B-informational)](#installation)

**Explicit, deterministic symbolic memory for AI systems via MCP (Model Context Protocol).**

SymbolicMemoryMCP provides a small MCP server that lets LLMs and agents **store and retrieve curated “ground truth”** by stable **symbols** (and optional aliases), instead of relying on probabilistic recall.

> **Store truth (semantics). Compute meaning when needed.**  
> This repo is a minimal, practical substrate for that idea.

---

## What you get

Repository contents:

- `server.py` — FastAPI-based MCP JSON-RPC server
- `client.py` — CLI client for manual save/get workflows
- `tests_smoke.py` — end-to-end MCP smoke tests
- `MCP2genericLLM.py` — reference LLM bridge (tested with Ollama)
- `LICENSE.md` — Business Source License (BUSL 1.1)

---

## Why this exists

Most LLM systems “remember” through:
- chat history (token-window limited)
- vector/RAG memory (approximate + heuristic)
- prompt state (drifts over time)

SymbolicMemoryMCP adds a complementary layer:
- **Deterministic recall** (no guessing)
- **Stable references** (symbols don’t drift)
- **Curated ground truth** (small, high-signal, human-verifiable)

### Recommended pattern: vector memory + symbolic memory
- **Vector memory**: broad, fuzzy “memory traces”
- **SymbolicMemoryMCP**: small, curated **definitions / invariants / policies** the agent must consult

---

## Relation to the JIT Symbolic Memory design pattern

SymbolicMemoryMCP is a **minimal implementation substrate** aligned with the **JIT Symbolic Memory** design pattern:

- **Context ≠ Memory** (memory is external and addressable)
- **Just-in-time retrieval** (memory is pulled only when needed)
- **No hidden prompt growth** (no background accumulation)
- The LLM is a reasoning engine, not a memory system

Design pattern (conceptual doc):
- https://github.com/Th3Hypn0tist/random/blob/main/jit-symbolic-memory-design-pattern

**Important licensing note**
- This repository is licensed under **BUSL 1.1** (see `LICENSE.md`).
- The **JIT Symbolic Memory design pattern** document has its own licensing terms (OPL/commercial) described in that document.
- Treat these as **separate**: repo license governs this code; the design-pattern doc governs use of that architecture description.

---

## Symbol model

A **symbol** is a stable, human-readable key.

Recommended convention:
- Uppercase segments separated by dots: `DOMAIN.SUBDOMAIN.NAME`
- Use suffixes for types: `.DEF`, `.RULE`, `.CFG`, `.ENUM`, `.NOTE`
- Prefer a small set of stable roots (don’t mint endless roots)

Examples:
- `HGI.DEF` — definition
- `USER.PREF.LANG` — user preference
- `POLICY.SAFETY.NO_SHELL_EXEC` — invariant/policy
- `PROJECT.SMMCP.ROADMAP.NOTE` — project note

### Aliases
Aliases are optional natural-language-friendly keys that resolve to the same entry.

Example:
- symbol: `HGI.DEF`
- aliases: `["hgi", "hybrid intelligence"]`

---

## Implemented MCP surface (v0.1.0)

### Save (write)
MCP method:
- `tools/call`

Tool name:
- `sm.texts.save`

Arguments example:
```json
{
  "symbol": "HGI.DEF",
  "text": "Hybrid General Intelligence = AI + human symbiosis",
  "cat": "ai",
  "subcat": "concepts.intelligence",
  "aliases": ["hgi", "hybrid intelligence"]
}
```

### Retrieve (read)
MCP method:
- `resources/read`

URI:
- `resource://sm/v1/texts/<symbol_or_alias>`

Examples:
- `resource://sm/v1/texts/HGI.DEF`
- `resource://sm/v1/texts/hybrid intelligence`

### Suggestions (best-effort)
If you save without `cat/subcat`, the server returns a best-effort `suggestions` block.

---

## Installation

Python 3.10+ recommended.

```bash
pip install fastapi uvicorn pydantic requests
```

---

## Run the server

```bash
uvicorn server:app --host 127.0.0.1 --port 8000
```

MCP endpoint:
```text
http://127.0.0.1:8000/mcp
```

---

## Smoke tests

Start the server, then:

```bash
python tests_smoke.py
```

Expected:
```text
OK: smoke tests passed
```

Smoke tests validate:
- MCP initialize handshake
- `sm.texts.save`
- `resources/read`
- alias resolution
- suggestion engine baseline

---

## CLI usage (client.py)

### Save a definition
```bash
python client.py save   --symbol HGI.DEF   --text "Hybrid General Intelligence = AI + human symbiosis"   --cat ai   --subcat concepts.intelligence   --aliases hgi "hybrid intelligence"
```

### Retrieve by symbol
```bash
python client.py get --symbol HGI.DEF
```

### Retrieve by alias
```bash
python client.py get --symbol "hybrid intelligence"
```

---

## LLM bridge usage (Ollama example)

Start services:
```bash
uvicorn server:app --port 8000
ollama serve
```

Run bridge:
```bash
python MCP2genericLLM.py   --backend ollama   --model llama3.1:8b   --mcp-url http://127.0.0.1:8000/mcp   --ollama-url http://127.0.0.1:11434/v1/chat/completions   --strict-get   --prompt "You MUST use tools. Save symbol TEST.BRIDGE with text 'bridge ok' in cat test subcat smoke.bridge and aliases ['bridge ok alias']. Then call sm_get using symbol TEST.BRIDGE."
```

Expected:
```text
bridge ok
```

### Reasoning prompt template (practical)
Use this to force consistent tool use:

```text
You MUST use the tools.
Before answering, resolve any important term via sm_get (symbol or natural-language alias).
If a required invariant/definition is missing, propose a symbol + aliases and store it via sm_save.
Answer strictly based on retrieved ground truth.
```

---

## How LLMs should use this in reasoning

### Call `sm_get` when
- a canonical definition is needed (avoid re-inventing terms)
- a policy/invariant constrains actions
- correctness depends on a stable config value

### Call `sm_save` when
- the user provides an explicit definition/invariant to persist
- you have a curated, stable definition worth reusing
- a “naming agent” decides a new canonical symbol + aliases

### Avoid silent invention
If a symbol doesn’t exist:
- ask the user to define it, or
- explicitly propose symbol + definition and store it (with confirmation in high-stakes systems)

---

## Storage & consistency

Current reference implementation is SQLite-backed.

Scope guarantees:
- single-process server
- transactional safety per write (SQLite)

Out of scope (for now):
- distributed replication
- multi-writer coordination across server instances
- versioned symbols, prefix search, batch ops (see Roadmap)

---

## Architecture

```text
LLM / Agent
  ↓ (tool calls)
MCP2genericLLM (bridge)
  ↓ (MCP JSON-RPC)
SM-MCP Server (FastAPI)
  ↓
SQLite Symbolic Store
```

This is framework-neutral and fits agent stacks that can do tool calls (e.g. OpenClaw/MoltBot-style ecosystems).

---

## Roadmap (documentation only)

Not implemented yet:
- prefix search (`HGI.*`)
- explicit alias management endpoints
- versioning (`HGI.DEF@v2`) + “current” alias pinning
- typed payloads (JSON schema per symbol)
- batch operations + export/import

Core philosophy: **small, deterministic core first**.

---

## License (this repository)

Business Source License 1.1 (BUSL 1.1)

- free for personal, educational, and research use
- commercial use requires a paid license
- converts to **GPL-2.0-or-later** after 3 years

See `LICENSE.md` for full terms.

---

## Author

Aki Hirvilammi
