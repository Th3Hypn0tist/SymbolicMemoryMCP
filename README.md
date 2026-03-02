# SymbolicMemoryMCP

## A Deterministic Knowledge Layer for LLM Systems

Most AI systems today rely on **probabilistic recall**.

They can retrieve similar information, but they cannot reliably:

- enforce invariants  
- guarantee factual grounding  
- provide auditability  
- separate truth from interpretation  

RAG improves retrieval — but it does not solve the core problem:

> **AI systems still lack a deterministic knowledge backbone.**

This project demonstrates a minimal approach to solving that gap.

---

## The Core Insight

Traditional AI memory works like this:

```
Store text → Inject into prompt → Model interprets probabilistically
```

Symbolic memory works differently:

```
Query → Deterministic identity lookup → Resolve ground truth → Inject just‑in‑time
```

The key distinction:

> **Memory is not stored context.  
> Memory is context resolved from ground truth.**

---

## What This Project Is

**SymbolicMemoryMCP** is a Proof‑of‑Concept implementation of a deterministic symbolic memory layer for AI systems.

It shows how knowledge can be:

- represented explicitly as symbols  
- resolved deterministically by identity  
- accessed through a protocol interface (MCP)  
- injected into AI workflows just‑in‑time  

Instead of putting memory inside the model, this approach treats memory as **infrastructure**.

---

## Quick Usage Examples

### 1. Store a Symbol

```python
from symbolic_memory import Memory

mem = Memory()
mem.put("RULE:MAX_TEMPERATURE", "Maximum safe temperature is 85°C")
```

### 2. Deterministic Lookup

```python
mem.get("RULE:MAX_TEMPERATURE")
```

Output:

```
Maximum safe temperature is 85°C
```

This lookup is:

- identity‑based  
- deterministic  
- invariant  

---

### 3. JIT Injection into LLM Context

```python
rule = mem.get("RULE:MAX_TEMPERATURE")

prompt = f"""
Use the following verified system rule:

{rule}

Now answer:
What is the maximum safe temperature?
"""
```

The model receives **resolved ground truth**, not probabilistic recall.

---

### 4. MCP Protocol Resolution Example

Example request:

```json
{
  "action": "resolve",
  "symbol": "RULE:MAX_TEMPERATURE"
}
```

Response:

```json
{
  "symbol": "RULE:MAX_TEMPERATURE",
  "value": "Maximum safe temperature is 85°C"
}
```

---

## Architectural Role

This operates at a different layer than typical AI memory systems.

| Layer | Purpose |
|------|---------|
| Assistant memory | Stores session context |
| Vector / RAG systems | Retrieve similar information |
| **Symbolic Memory** | Provides deterministic invariants |

Symbolic memory does not replace RAG or context memory.  
It complements them by acting as the **system knowledge backbone**.

---

## Identity vs Similarity

### Vector Memory
- similarity‑based  
- fuzzy recall  
- probabilistic  

### Symbolic Memory
- identity‑based  
- invariant  
- deterministic  

This enables a clean separation between:

- probabilistic reasoning  
- deterministic truth  

---

## What Makes This Deterministic

Symbols resolve by identity — not similarity.

This guarantees:

- invariant grounding  
- explicit knowledge boundaries  
- reproducible resolution  
- auditability  

The system always knows **why** a fact was used.

---

## Technology‑Neutral by Design

The symbolic layer can be implemented using:

- key‑value stores  
- relational databases  
- graph databases  
- embedded storage  
- cloud or local runtimes  

---

## Relationship to the JIT Symbolic Memory Design Pattern

This repository is a **Proof of Concept (PoC)** implementation inspired by the **JIT Symbolic Memory** design pattern.

It is important to understand the distinction:

- The design pattern defines **architectural principles**.  
- This project demonstrates **one minimal technical realization** of those principles.

The design pattern itself is conceptual and intentionally non‑prescriptive.

Link to the design pattern:  
https://github.com/Th3Hypn0tist/random/blob/main/jit-symbolic-memory-design-pattern

---

## JIT Resolution Example

1. AI needs a known invariant.  
2. Queries symbolic layer via MCP.  
3. Symbol resolves deterministically.  
4. Ground truth injected into context.  
5. Model reasons using controlled knowledge.

---

## What This PoC Demonstrates

- Deterministic symbolic lookup  
- Separation of reasoning and truth layers  
- Protocol‑based knowledge access  
- Minimal infrastructure footprint  

---

## What This Is NOT

- a full memory system  
- a vector database replacement  
- a knowledge graph engine  
- production‑ready storage  

---

## In One Sentence

AI models reason probabilistically.  
Systems still need something that does not.

---

## License

This project is released under the **Business Source License (BUSL)**.

### What this means

You are free to:

- use the software for personal and internal purposes  
- experiment, evaluate, and prototype freely  
- build non-commercial integrations  

Commercial use requires a separate license.

The intent is to:

- enable broad experimentation and adoption  
- protect the long-term sustainability of the project  
- prevent uncredited commercial cloning  

See the LICENSE file for full terms.
