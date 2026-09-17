# 🚀 Production AI Chat API

A production-grade, secure, and observable AI Agent API powered by **FastAPI**, **LangGraph**, **LangChain**, and **LiteLLM**. Built for high reliability, fast response times, and hardened security.

---

## 🌟 Key Features

- **Multi-Model LLM Resilience**: Primary and Fallback model architecture using [LiteLLM](https://github.com/BerriAI/litellm) (configured for NVIDIA NIM, OpenAI, Anthropic, or self-hosted models) orchestrated by **LangGraph** with automated retry mechanisms.
- **Security & Safety Guardrails**:
  - **Prompt Injection Defense**: Detection and mitigation of jailbreaking and prompt injection patterns.
  - **Input Sanitization**: Delimiter striping and syntax filtering.
  - **Bidirectional PII Masking**: Automatically redacts emails, credit cards, SSNs, phone numbers, and IP addresses across both incoming prompts and LLM-generated responses.
  - **Harmful Content Filtering**: Output inspection to prevent harmful responses.
- **High-Performance In-Memory Response Caching**: Normalized SHA-256 caching with TTL to reduce LLM costs by 30–60% and deliver sub-millisecond responses on repeated queries.
- **Rate Limiting & Abuse Prevention**: IP-based rate limiting powered by `slowapi` to protect upstream quotas.
- **Production Observability & Monitoring**:
  - Structured JSON logging for cloud log aggregators (Datadog, CloudWatch, Grafana Loki).
  - Runtime metrics collection (`/metrics`) tracking total requests, error rate, average latency, token estimates, and cache hit rate.
  - Full trace integration with **LangSmith** (`LANGCHAIN_TRACING_V2`).
- **Container & Orchestrator Ready**: Dedicated `/health` endpoint for Docker and Kubernetes readiness/liveness probes.
- **Modern Python Tooling**: Managed with [**uv**](https://github.com/astral-sh/uv) for blazing-fast dependency resolution and virtual environments.

---

## 🏗️ Architecture & Request Lifecycle

```
Client Request (POST /chat)
         │
         ▼
 ┌──────────────────────┐
 │  Rate Limiter Check  │ ──► (429 Too Many Requests if exceeded)
 └──────────┬───────────┘
         │
         ▼
 ┌──────────────────────┐
 │   Security Pipeline  │ ──► (400 Bad Request if Prompt Injection detected)
 │ (Sanitize & Mask PII)│
 └──────────┬───────────┘
         │
         ▼
 ┌──────────────────────┐   Hit
 │ Response Cache Check │ ───────► Return Cached Response (0 ms)
 └──────────┬───────────┘
         │ Miss
         ▼
 ┌──────────────────────┐
 │  LangGraph Agent     │
 │  ┌────────────────┐  │
 │  │ Primary Model  │  │
 │  └───────┬────────┘  │
 │          │ (On Failure / Retry Budget)
 │          ▼           │
 │  ┌────────────────┐  │
 │  │ Fallback Model │  │
 │  └───────┬────────┘  │
 │          │ (Max Retries Exceeded)
 │          ▼           │
 │  ┌────────────────┐  │
 │  │ Error Handler  │  │
 │  └────────────────┘  │
 └──────────┬───────────┘
         │
         ▼
 ┌──────────────────────┐
 │  Output Validation   │ (Sanitize & Mask PII in AI Response)
 └──────────┬───────────┘
         │
         ▼
 ┌──────────────────────┐
 │ Cache Store & Record │ (Update cache, collect latency & token metrics)
 └──────────┬───────────┘
         │
         ▼
   JSON Response
```

---

## 📁 Project Structure

```text
production-api/
├── app/
│   ├── __init__.py
│   ├── agent.py         # LangGraph state graph with primary/fallback fallback logic
│   ├── cache.py         # ResponseCache with SHA-256 key hashing & TTL
│   ├── config.py        # Pydantic Settings for validated environment variables
│   ├── main.py          # FastAPI application, lifecycle, rate limiting & routes
│   ├── models.py        # Pydantic schemas (ChatRequest, ChatResponse, Health, Metrics)
│   ├── monitoring.py    # Structured JSON logger & MetricsCollector
│   └── security.py      # Prompt injection scanner, PII detector & output validator
├── .env                 # Environment secrets & runtime configuration (git-ignored)
├── .env.example         # Example environment configuration template
├── pyproject.toml       # Project metadata and dependencies
├── uv.lock              # Lockfile for deterministic dependency resolution
└── README.md            # Project documentation
```

---

## ⚙️ Environment Variables (`.env`)

Create a `.env` file in the root directory by copying `.env.example`:

```bash
cp .env.example .env
```

### Configuration Details

| Variable | Type | Default | Description |
| :--- | :---: | :--- | :--- |
| `LITELLM_PRIMARY_CHAT_MODEL` | `str` | `nvidia_nim/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | LiteLLM model identifier for the primary LLM |
| `LITELLM_FALLBACK_CHAT_MODEL` | `str` | `nvidia_nim/deepseek-ai/deepseek-v4-flash-0731` | LiteLLM model identifier used when the primary model fails |
| `LITELLM_CHAT_API_KEY` | `str` | **Required** | API key for the chat model provider (e.g., NVIDIA NIM, OpenAI, Anthropic) |
| `LITELLM_EMBEDDING_MODEL` | `str` | `nvidia_nim/nvidia/nemotron-3-embed-1b` | LiteLLM embedding model identifier |
| `LITELLM_EMBEDDING_API_KEY` | `str` | **Required** | API key for the embeddings model provider |
| `LANGCHAIN_TRACING_V2` | `bool`| `false` | Enable or disable LangSmith tracing (`true` / `false`) |
| `LANGCHAIN_API_KEY` | `str` | **Required** | LangSmith API key (required if tracing is enabled) |
| `LANGCHAIN_PROJECT` | `str` | `production-api-project` | Project name displayed in the LangSmith dashboard |
| `APP_ENV` | `str` | `development` | Environment mode (`development`, `staging`, `production`) |
| `LOG_LEVEL` | `str` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `RATE_LIMIT` | `str` | `20/minute` | Rate limit format parsed by `slowapi` (e.g., `20/minute`, `100/hour`) |
| `CACHE_TTL_SECONDS` | `int` | `300` | In-memory cache time-to-live in seconds (e.g., 300 = 5 min) |
| `MAX_RETRIES` | `int` | `3` | Maximum retry attempts inside the LangGraph state machine before returning a graceful error |

---

## 🚀 Getting Started with `uv`

This project uses [**`uv`**](https://docs.astral.sh/uv/), the extremely fast Python package and environment manager.

### 1. Prerequisites

- Python `>= 3.14` installed on your machine.
- `uv` installed. If you don't have it yet, install it via:
  - **Windows (PowerShell)**:
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
  - **macOS / Linux**:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

### 2. Clone and Setup Environment

Clone the repository and navigate to the project directory:

```bash
git clone <repository-url>
cd production-api
```

Install all dependencies from the lockfile and create the virtual environment:

```bash
uv sync
```

### 3. Configure Credentials

Create and configure your `.env` file:

```bash
cp .env.example .env
```

Open `.env` and configure your API keys (e.g. `LITELLM_CHAT_API_KEY`, `LANGCHAIN_API_KEY`).

---

## 🏃 Running the Application

### Development Server (with Auto-Reload)

Run the server with Uvicorn using `uv run`:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The application will start on `http://127.0.0.1:8000`.

- **Swagger Interactive API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Production Server

For production environments, run Uvicorn with multiple workers without reload:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 📡 API Endpoints & Usage

### 1. Chat Completion (`POST /chat`)

Sends a prompt to the AI agent.

#### Request
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, can you explain what microservices are?",
    "thread_id": "session-123"
  }'
```

#### Response (`200 OK`)
```json
{
  "response": "Microservices is an architectural approach where an application is arranged as a collection of loosely coupled, independently deployable services...",
  "thread_id": "session-123",
  "model_used": "primary",
  "cached": false,
  "processing_time_ms": 782.45,
  "timestamp": "2026-09-17T17:15:30.123456+00:00",
  "security_notes": []
}
```

> **Note on PII**: If a user submits sensitive information (such as `contact me at user@example.com`), the API masks it before sending it to the model and includes notes in `security_notes`:
> ```json
> {
>   "security_notes": ["[PII Masked] email detected and masked"]
> }
> ```

---

### 2. Health Check (`GET /health`)

Returns component health status for Docker and Kubernetes health probes.

#### Request
```bash
curl -X GET http://127.0.0.1:8000/health
```

#### Response (`200 OK`)
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "1.0.0",
  "checks": {
    "agent": true,
    "security": true,
    "cache": true
  }
}
```

---

### 3. Monitoring Metrics (`GET /metrics`)

Provides aggregated application health, throughput, and cache efficiency statistics.

#### Request
```bash
curl -X GET http://127.0.0.1:8000/metrics
```

#### Response (`200 OK`)
```json
{
  "total_requests": 42,
  "total_errors": 0,
  "error_rate": "0.00%",
  "avg_latency_ms": 312.18,
  "cache_hit_rate": "38.10%",
  "total_input_tokens": 1240,
  "total_output_tokens": 4820
}
```

---

### 4. Cache Statistics (`GET /cache/stats`)

Inspects the in-memory cache size, hit/miss ratios, and TTL configuration.

#### Request
```bash
curl -X GET http://127.0.0.1:8000/cache/stats
```

#### Response (`200 OK`)
```json
{
  "total_entries": 16,
  "hits": 16,
  "misses": 26,
  "hit_rate": "38.10%",
  "ttl_seconds": 300
}
```

---

## 🛡️ Security Features in Action

| Threat | Handling Strategy | Status Code |
| :--- | :--- | :---: |
| **Prompt Injection** (e.g. `ignore all previous instructions`) | Regex pattern matching + rejection | `400 Bad Request` |
| **PII Leakage** (Email, Credit Card, SSN, Phone, IP) | Bidirectional regex replacement with `[REDACTED_*]` tags | `200 OK` (Masked) |
| **Volumetric Abuse / DoS** | IP-level sliding window rate limiting via `slowapi` | `429 Too Many Requests` |
| **Model Outage / 5xx from Provider** | Automatic failover to secondary fallback LLM | `200 OK` (Fallback) |

---

## 🧪 Development & Testing

Run tests or arbitrary Python scripts in the project virtual environment with `uv run`:

```bash
# Add new dependencies
uv add package-name

# Run test commands
uv run pytest
```

---

## 📄 License

This project is licensed under the MIT License.
