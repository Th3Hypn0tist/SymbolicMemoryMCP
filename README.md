# SymbolicMemoryMCP

**Explicit, deterministic symbolic memory for AI systems via MCP (Model Context Protocol).**

SymbolicMemoryMCP turns “AI memory” from implicit, probabilistic recall into **explicit, addressable knowledge**:
store text by stable **symbols** (e.g. `HGI.DEF`) and retrieve it deterministically.

---

## What this is (and isn’t)

**This is**
- A small MCP server that provides **read/write** of curated “ground truth” snippets by symbol
- A reference **bridge** showing how tool-calling LLMs can use MCP-backed symbolic memory
- A workflow for **explicit definitions / invariants** that the LLM should not re-interpret

**This is not**
- A vector store / fuzzy semantic memory
- A full “knowledge base” with search, listing, or schema enforcement (see Roadmap)

---

## Why this matters

Most LLM systems “remember” through:
- chat history (token-window limited)
- RAG/vector memory (approximate + heuristic)
- ad-hoc prompts (drift over time)

SymbolicMemoryMCP provides a complementary layer:
- **Deterministic recall** (no guessing)
- **Stable references** (symbols don’t change unless you change them)
- **Curated ground truth** (small, high-signal, human-verifiable)

### Recommended pattern: Vector memory + Symbolic memory
- **Vector memory**: broad, fuzzy, “memory trace”
- **SymbolicMemoryMCP**: small, curated **invariants / definitions / policies** the agent must consult

---

## Symbol model

A **symbol** is a stable, human-readable key.

### Recommended naming rules (convention)
- Uppercase segments separated by dots: `DOMAIN.SUBDOMAIN.NAME`
- Use suffixes for types: `.DEF`, `.RULE`, `.CFG`, `.ENUM`, `.NOTE`
- Prefer **few** stable roots rather than endless unique roots

Examples:
- `HGI.DEF` — definition
- `USER.PREF.LANG` — user preference
- `POLICY.SAFETY.NO_SHELL_EXEC` — invariant/policy
- `PROJECT.SMMCP.ROADMAP.NOTE` — project note

### Aliases
Aliases are optional, natural-language-friendly keys that resolve to the same entry.
Example: `aliases=["hgi","hybrid intelligence"]`

---

## What operations exist today (v0.1.0)

**Implemented**
- `sm.texts.save` (MCP `tools/call`) — create/update a symbol with optional `cat`, `subcat`, `aliases`
- `resource://sm/v1/texts/<symbol_or_alias>` (MCP `resources/read`) — retrieve by symbol **or alias**
- Suggestion engine (when saving without taxonomy) — returns suggested `cat/subcat` (best-effort)

**Not implemented (documented as ideas / roadmap)**
- list, find-by-prefix (`HGI.*`), tags, batch ops
- explicit alias management endpoints (set/remove)
- versioning (`HGI.DEF@v2`) and alias pinning
- structured payload schemas (JSON schema per symbol)

Keeping this v0.1.0 surface small is intentional: **boring core first**.

---

## Storage & consistency

Current reference implementation is SQLite-backed.

Practical guarantees (current scope):
- Single-process server → operations are consistent within that process
- SQLite provides transactional safety for individual writes

Out of scope (for now):
- multi-node replication
- explicit migrations API
- concurrent writers across multiple server instances

---

## How an LLM should use this in reasoning

### Mental model
Treat SymbolicMemoryMCP as **ground truth snapshots**:
- definitions
- invariants/policies
- stable config values
- “never reinterpret” facts

### When to call `sm_get`
Call `sm_get` whenever:
- a term is important and must match a canonical meaning (`HGI`, `PrimeSL`, etc.)
- a policy/invariant might constrain actions
- the LLM is about to produce an answer where correctness depends on a fixed rule

### When to call `sm_save`
Call `sm_save` when:
- the user provided an explicit definition/invariant and asked to store it
- the system produced a curated “final” definition worth reusing
- a stable preference/config was stated and should persist

### Avoid “silent invention”
If no symbol exists:
- either ask the user to define it
- or propose a symbol + definition explicitly and store it (with user confirmation in high-stakes systems)

---

## Natural language → symbol key (naming layer)

This is the main missing piece if you want the system to feel “non-manual”.

**v0.1.0 approach (documented convention)**
- Humans (or a “naming agent”) choose symbols once
- LLM uses **aliases** to resolve natural language to the correct entry

Example:
- User asks: “What does hybrid intelligence mean here?”
- LLM calls: `sm_get(symbol="hybrid intelligence")` → alias resolves to `HGI.DEF`

### Naming agent (recommended architecture addon)
Add a small “naming agent” whose job is:
- propose a symbol for a new concept
- attach aliases
- keep the symbol space consistent across many agents

This can be done without changing SymbolicMemoryMCP:
- it’s just a policy/tooling layer in front of `sm_save`

---

## Quick start

### Install
```bash
pip install fastapi uvicorn pydantic requests
```

### Run server
```bash
uvicorn server:app --host 127.0.0.1 --port 8000
```

MCP endpoint:
```text
http://127.0.0.1:8000/mcp
```

---

## CLI examples (client.py)

### Save a definition (DEFINE → store)
```bash
python client.py save \
  --symbol HGI.DEF \
  --text "Hybrid General Intelligence = AI + human symbiosis" \
  --cat ai \
  --subcat concepts.intelligence \
  --aliases hgi "hybrid intelligence"
```

### Get by symbol
```bash
python client.py get --symbol HGI.DEF
```

### Get by alias
```bash
python client.py get --symbol "hybrid intelligence"
```

---

## Smoke tests

### MCP-only smoke test
```bash
python tests_smoke.py
```

Expected:
```text
OK: smoke tests passed
```

---

## LLM bridge smoke test (Ollama)

Start services:
```bash
uvicorn server:app --host 127.0.0.1 --port 8000
ollama serve
```

Run:
```bash
python MCP2genericLLM.py \
  --backend ollama \
  --model llama3.1:8b \
  --mcp-url http://127.0.0.1:8000/mcp \
  --ollama-url http://127.0.0.1:11434/v1/chat/completions \
  --strict-get \
  --prompt "You MUST use tools. Save symbol TEST.BRIDGE with text 'bridge ok' in cat test subcat smoke.bridge and aliases ['bridge ok alias']. Then call sm_get using symbol TEST.BRIDGE."
```

Expected:
```text
bridge ok
```

### “Reasoning style” prompt template
Use this to get consistent tool usage:
```text
You MUST use the tools.
Before answering, resolve any important term via sm_get using either a symbol or a natural-language alias.
If a needed invariant/definition is missing, propose a symbol and store it via sm_save with aliases.
Then answer based strictly on the retrieved ground truth.
```

---

## Architecture

```text
LLM / Agent
  ↓ (tool calls)
MCP2genericLLM (bridge)
  ↓ (MCP JSON-RPC)
SM-MCP server (FastAPI)
  ↓
SQLite (symbolic store)
```

This is framework-neutral and fits agent ecosystems that can do tool calls (e.g. OpenClaw/MoltBot-style stacks).

---

## Roadmap (documentation only)

These are **ideas**, not claims about current features:

- `sm_list(cat?, subcat?)`
- `sm_find_prefix(prefix="HGI.")`
- explicit alias management (`alias_set`, `alias_remove`)
- versioning (`HGI.DEF@v2`) + “current” alias pinning
- typed payloads (JSON schema per symbol)
- batch ops and export/import

---
## Relationship to the JIT Symbolic Memory Design Pattern

This repository is a **Proof of Concept (PoC)** implementation inspired by the **JIT Symbolic Memory** design pattern.

It is important to understand the distinction:

- The design pattern defines **architectural principles**.
- This project demonstrates **one minimal technical realization** of those principles.

The JIT Symbolic Memory document itself is explicitly conceptual and intentionally non-prescriptive. It does **not** describe an implementation, reference architecture, or technical specification.

This repository therefore should be read as:

> A practical illustration of how a deterministic symbolic memory layer can be built and integrated into an AI system using a simple protocol interface.

It represents **one possible implementation path**, not the pattern itself.

Different systems may implement the same architectural model using:

- different storage technologies
- different deployment environments
- different protocol layers
- different internal structures

The purpose of this PoC is to make the architectural idea concrete, testable, and understandable in real-world system design.
https://github.com/Th3Hypn0tist/random/blob/main/jit-symbolic-memory-design-pattern
---

## License

Business Source License 1.1 (BUSL 1.1).  
Free for private use. Paid for business use. Converts to open source after 3 years.

See `LICENSE.md`.

---

## Author

Aki Hirvilammi
