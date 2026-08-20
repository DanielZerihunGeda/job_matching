# Job Matching Platform

A platform for secure candidate document ingestion, structured profile extraction, and intelligent job-to-candidate matching. Built with FastAPI, PostgreSQL, and Neo4j.

## Overview

The platform provides two core capabilities that work together:

**Candidate Ingestion Pipeline** — Securely ingest candidate documents (resumes, CVs), extract structured profile data using LLMs, and project a rich, queryable knowledge graph in Neo4j with full provenance and alias resolution.

**Intelligent Candidate Matching** — Given a job description, extract structured search intent, resolve canonical skill/role/location identifiers, and rank candidates using a deterministic blend of exact structured signals and semantic similarity — all without the LLM ever writing queries or computing scores.

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CANDIDATE INGESTION PIPELINE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────────┐   │
│  │  Ingest API  │    │  Validation &    │    │  Background Workers    │   │
│  │              │    │  Sanitization    │    │                        │   │
│  │  • Auth +    │───▶│                  │───▶│  ┌──────────────────┐ │   │
│  │    Idempotency│    │  • ClamAV scan   │    │  │ Parsing Worker   │ │   │
│  │  • Size/type │    │  • Text extract  │    │  │  • Trusted text  │ │   │
│  │    limits    │    │    & sanitize    │    │  │    isolation     │ │   │
│  └──────────────┘    │  • Hidden artifact│    │  │  • Strict JSON   │ │   │
│                      │    detection     │    │  │    schema + retries│ │   │
│                      │  • Prompt inj.   │    │  │  • Embeddings    │ │   │
│                      │    guardrails    │    │  └────────┬─────────┘ │   │
│                      └────────┬─────────┘    │           │           │   │
│                               │              │  ┌────────▼─────────┐ │   │
│                               │              │  │ Graph Projector  │ │   │
│                               │              │  │  • Atomic upsert │ │   │
│                               │              │  │  • Alias resolve │ │   │
│                               │              │  │  • Provenance    │ │   │
│                               │              │  └────────┬─────────┘ │   │
│                               │              └───────────┼───────────┘   │
│                               ▼                              ▼             │
│                      ┌─────────────────┐           ┌─────────────────┐   │
│                      │  PostgreSQL     │           │      Neo4j      │   │
│                      │  (Durable Queue)│           │  Candidate Graph│   │
│                      └─────────────────┘           └─────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CANDIDATE MATCHING SERVICE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐   ┌────────────────┐   ┌─────────────┐   ┌────────────┐  │
│  │  Match API  │──▶│ Intent Extract │──▶│  Alias      │──▶│  Search    │  │
│  │  (Job Desc) │   │  (LLM + strict │   │  Resolution │   │  Plan      │  │
│  └─────────────┘   │   schema)      │   │  (Catalog + │   │  (Hard +   │  │
│                    └────────────────┘   │   Fuzzy)    │   │   Weighted)│  │
│                                         └─────────────┘   └─────┬──────┘  │
│                                                                   │         │
│                    ┌────────────────┐   ┌─────────────┐           │         │
│                    │  Scoring       │◀───│  Retrieval  │◀──────────┘         │
│                    │  (Deterministic)    │  (Neo4j)    │                     │
│                    │  • Structured    │   │  • Facts    │                     │
│                    │  • Semantic      │   │  • Embeddings│                    │
│                    └────────┬─────────┘   └─────────────┘                     │
│                             ▼                                                │
│                    ┌────────────────┐                                         │
│                    │  Ranked        │                                         │
│                    │  Matches       │                                         │
│                    └────────────────┘                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Ingestion Security Layers**: The pipeline implements defense-in-depth against adversarial documents:
1. **Edge validation** — Size limits, content-type checks, ClamAV malware scanning
2. **Text extraction & sanitization** — Strips hidden text, zero-width chars, invisible Unicode, embedded objects
3. **Prompt injection guardrails** — Heuristic detection of instruction-like patterns, delimiter confusion, role-play attempts in extracted text
4. **Trusted-text isolation** — Only sanitized, validated text reaches the LLM; system prompt enforces "extract only facts present in the trusted visible resume text"
5. **Strict JSON schema + bounded retries** — Provider-enforced structured output prevents schema deviation; validation failures trigger targeted re-prompting (max N attempts)

## Key Capabilities

### Secure Document Ingestion
- **Authenticated API** with idempotency keys for safe retries
- **Malware scanning** via ClamAV on every upload
- **Size limits** and content-type validation at the edge
- **Structured LLM parsing** with bounded retries and schema validation
- **Durable PostgreSQL queue** with lease-based processing and exponential backoff

### Rich Candidate Profiles
- **Comprehensive extraction**: skills, roles, projects, certifications, languages, locations
- **Relationship preservation**: role↔skill, project↔skill, role↔organization linkage
- **Canonical identity**: stable IDs, aliases, and fuzzy resolution for skills, organizations, locations, certifications
- **Embeddings** on roles and projects for semantic search

### Deterministic Job Matching
- **LLM-powered intent extraction** — converts free-text job descriptions into structured requirements (skills, experience, location, certifications, etc.)
- **Alias catalog resolution** — maps observed terms to canonical keys using a maintained catalog with fuzzy fallback
- **Hybrid search plan** — hard constraints (mandatory requirements) + weighted structured signals + semantic queries
- **Two-path scoring**:
  - *Structured*: exact canonical key matches for skills, roles, certifications, locations, languages
  - *Semantic*: cosine similarity on role/project embeddings for "meaning" queries
- **Weighted aggregation** with evidence coverage — final score = Σ(signal_score × weight) / Σ(weights)
- **Transparent output** — every match includes per-signal scores, match methods, and a summary

### Operational Excellence
- **Health endpoints** (`/live`, `/ready`) with dependency checks (PostgreSQL, Neo4j, ClamAV, LLM, embeddings, workers, queue depth)
- **Prometheus metrics** at `/health/metrics`
- **OpenTelemetry tracing** and structured JSON logging
- **Database migrations** applied automatically at startup
- **Neo4j schema management** with indexes and constraints
- **Graceful worker shutdown** with drain semantics

## Quick Start

### With Docker Compose (Recommended)

```bash
# 1. Configure environment
cp -n .env.example .env
# Edit .env with your credentials (LLM, embeddings, Neo4j, PostgreSQL, ClamAV)

# 2. Start all services
docker compose up --build

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs (if enabled)
```

### Local Development

```bash
# Install locked dependencies
uv sync

# Run with auto-reload (requires running Postgres, Neo4j, ClamAV separately)
uv run fastapi dev
```

## Configuration

Create `.env` from `.env.example`. All credentials must be provided — Compose will reject startup with placeholders.

Configuration groups:

| Prefix | Purpose |
|--------|---------|
| `APP_*` | FastAPI settings, service authentication, environment |
| `POSTGRES_*` | PostgreSQL connection, pool tuning, migrations |
| `NEO4J_*` | Neo4j connection, database, pool, fuzzy thresholds |
| `UPLOAD_*`, `WORKER_*`, `EXTRACTION_*` | Ingestion limits, worker concurrency, parsing bounds |
| `LLM_*` | Structured-output provider (endpoint, model, API key, schema version) |
| `EMBEDDING_*` | Embedding provider for semantic search |
| `SEARCH_*` | Candidate set limits, exact/ANN thresholds, result caps |
| `OBSERVABILITY_*` | Tracing, metrics namespace, commit/build metadata |

**Production note**: Set `APP_ENVIRONMENT=production` only with a certificate-verified `neo4j+s://` or `bolt+s://` endpoint — enforced at startup.

## API Reference

### Health & Observability

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/v1/health/live` | None | Liveness probe |
| `GET /api/v1/health/ready` | Bearer token | Readiness with full dependency status |
| `GET /api/v1/health/metrics` | Bearer token | Prometheus metrics |

### Candidate Ingestion

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/v1/candidate-ingestions` | Bearer token | Submit document for processing (multipart: `document`, `telegramId`, `sourceMessageId`; headers: `Idempotency-Key`, optional `X-Document-Size`) |
| `GET /api/v1/candidate-ingestions/{job_id}` | Bearer token | Check ingestion status (QUEUED, PARSING, PROJECTING, COMPLETED, FAILED) |

### Candidate Matching

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /api/v1/candidate-matches` | Bearer token | Match candidates to a job description |

**Request**:
```json
{
  "jobDescription": "Senior Python Engineer with 5+ years...",
  "scoreThreshold": 0.6,
  "resultLimit": 20
}
```

**Response** (abridged):
```json
{
  "intentSchemaVersion": "1.0.0",
  "searchPlanVersion": "2024.01.15",
  "aliasCatalogVersion": "2024.01.10",
  "normalizerVersion": "2024.01.01",
  "planComplete": true,
  "provisional": false,
  "unresolvedMandatoryRequirements": [],
  "matches": [
    {
      "candidateId": "cand-abc123",
      "finalScore": 0.87,
      "evidenceCoverage": 0.78,
      "structuredSignals": [
        {"signalId": "skill-python", "category": "structured", "score": 1.0, "evidencePresent": true, "matchMethod": "canonical_key"},
        {"signalId": "exp-years", "category": "structured", "score": 0.8, "evidencePresent": true, "matchMethod": "range_ratio"}
      ],
      "semanticSignals": [
        {"signalId": "role-meaning", "category": "semantic", "score": 0.92, "evidencePresent": true, "matchMethod": "exact_cosine_max"}
      ],
      "matchSummary": ["skill-python:canonical_key", "role-meaning:exact_cosine_max", "exp-years:range_ratio"]
    }
  ]
}
```

## How Matching Works (Conceptual)

1. **Extract Intent** — LLM reads the job description and outputs structured requirements with types (skill, experience, location, certification, language, role_title, industry, employment_type, proficiency) plus semantic "meaning" queries for roles/projects.

2. **Resolve Aliases** — Each requirement is mapped to a canonical key via the alias catalog (exact, alias, or fuzzy Levenshtein). Unresolved mandatory requirements are flagged.

3. **Build Search Plan** — Hard constraints (mandatory structured signals) filter the candidate pool first. Remaining signals become weighted scoring inputs; semantic queries become vector searches.

4. **Retrieve & Score** —
   - Fetch candidate facts from Neo4j (skills, roles, locations, certifications, languages, experience tenures, embeddings)
   - Compute structured scores (1.0 for canonical match, 0 otherwise; range ratio for experience)
   - Compute semantic scores via exact cosine or ANN on role/project embeddings
   - Aggregate with weights, filter by threshold, sort by score → coverage → candidate_id

5. **Return** — Ranked matches with per-signal breakdown, evidence coverage, and a human-readable summary.

**Determinism guarantee**: The LLM never writes Cypher, never computes scores, and never ranks. It only extracts intent. All retrieval, scoring, and ranking are pure deterministic code.

## Testing

```bash
# Lint
uv run ruff check .

# Unit tests
uv run pytest

# Integration tests (require TEST_POSTGRES_DSN, TEST_NEO4J_*)
uv run pytest -m integration
```

## Project Structure

```
src/job_matching/
├── api/
│   ├── v1/
│   │   ├── ingestions.py      # Candidate ingestion endpoints
│   │   └── matches.py         # Candidate matching endpoint
│   ├── dependencies.py        # FastAPI dependency providers
│   ├── errors.py              # Error handlers
│   └── router.py              # Route composition
├── core/
│   ├── config.py              # Pydantic Settings (all env groups)
│   ├── lifespan.py            # Startup/shutdown lifecycle
│   └── runtime.py             # ApplicationRuntime (workers, connectors, services)
├── db/
│   ├── neo4j.py               # Neo4j connector + session management
│   ├── neo4j_schema.py        # Schema DDL (constraints, indexes, vector)
│   ├── postgres.py            # PostgreSQL connector + pool
│   └── __init__.py
├── domain/
│   └── ingestion.py           # Domain errors, error codes
├── repositories/
│   ├── ingestion.py           # Job queue CRUD, status
│   ├── processing.py          # Parsed profile persistence
│   └── matching.py            # Candidate facts retrieval, semantic search
├── schemas/
│   ├── ingestion.py           # Ingestion request/response models
│   ├── matching.py            # Matching request/response, search plan, signals
│   └── profile.py             # Parsed profile, LLM profile schemas
├── security/
│   ├── auth.py                # Service identity (Bearer token)
│   ├── clamav.py              # ClamAV client
│   └── body_limit.py          # Request size middleware
├── services/
│   ├── matching.py            # CandidateMatchingService (orchestration, scoring)
│   ├── parsing.py             # LLM resume parsing with validation retries
│   ├── projection.py          # Neo4j graph projection (atomic, replay-safe)
│   ├── search_intent.py       # Search intent resolution, plan compilation
│   ├── search_extraction.py   # LLM job description → structured intent
│   ├── aliases.py             # Alias catalog, canonical keys, fuzzy resolution
│   ├── embeddings.py          # Embedding provider + enrichment
│   └── normalization.py       # Text normalization, Levenshtein, composite keys
├── workers/
│   ├── parsing_worker.py      # Lease-based parsing + embedding loop
│   └── graph_worker.py        # Lease-based graph projection loop
├── main.py                    # FastAPI app factory
└── observability.py           # Logging, tracing, metrics
```

## License


---

## TODO / Roadmap

- [ ] **RedisVL semantic caching for candidate matching** — Cache embedding lookups and match results using Redis Vector Library (RedisVL) to accelerate repeated job description queries. Semantic cache keys derived from normalized intent hashes; TTL and invalidation tied to candidate graph projection snapshots.

- [ ] **Telegram bot service integration** — Expose ingestion and matching via a Telegram bot: `/start` onboarding, document forwarding for ingestion, `/match <job description>` for interactive candidate search, status notifications on ingestion completion, and webhook-based deployment for production.
