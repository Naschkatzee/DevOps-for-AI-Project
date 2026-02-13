# DevOps for AI – Vacation Agent Service

## Project Overview

This project was developed for the university course **“DevOps for AI.”**

It implements an AI-powered vacation planning service and demonstrates how a Large Language Model (LLM) can be integrated into a structured, controlled, observable, and reproducible backend system.

The goal of this project is not just to use AI, but to show how AI systems can be engineered using professional DevOps principles.

---

## Core Idea

The system combines:

- Probabilistic AI (LLM reasoning)
- Deterministic backend logic
- Schema validation
- External tool integration
- Monitoring and logging
- Containerization for reproducibility

Instead of building a chatbot, this project builds a **controlled AI agent service**.

---

## What the Service Does

The API receives a natural language request such as:

> “I want a 4-day trip in May to Barcelona, budget €800, I like culture and food, starting from Berlin.”

The system then:

1. Parses the request using a local LLM (Ollama)
2. Validates the structured output using Pydantic schemas
3. Applies deterministic decision logic
4. Calls external APIs (Open-Meteo for weather)
5. Generates a day-by-day itinerary using the LLM
6. Logs execution details for traceability
7. Exposes metrics for monitoring
8. Returns a structured JSON response

This ensures AI output is controlled, validated, and observable.

---

## Architecture

### Technology Stack

- **FastAPI** – REST API framework
- **Ollama** – Local LLM runtime
- **Pydantic** – Schema validation
- **Open-Meteo** – Weather API
- **Prometheus Client** – Metrics
- **Docker** – Containerization

### Processing Flow

User → API → LLM → Schema Validation → Decision Logic → External Tools → Itinerary Generation → Audit Log + Metrics → JSON Response

---

## DevOps Implementation Steps

### Step 1 – Service Skeleton

- FastAPI application
- `/docs`
- `/healthz`
- `/readyz`

**Meaning:** Establish a production-style API structure with health endpoints and API documentation.

---

### Step 2 – Input Validation

- Defined `PlanRequest` schema
- Validated user input before processing

**Meaning:** Prevent invalid/unsafe inputs and ensure the system fails early with clear errors.

---

### Step 3 – Structured LLM Parsing

- LLM converts free text into structured JSON
- Output validated using Pydantic models (with normalization)

**Meaning:** Make AI output deterministic and testable by forcing a strict schema.

---

### Step 4 – Deterministic Decision Logic

- Explicit `if/else` rules determine which tools to call
- AI does not control system flow

**Meaning:** Predictable control and safer agent behavior (LLM supports the pipeline, but does not run it).

---

### Step 5 – External Tool Integration

- Geocoding API (Open-Meteo geocoding)
- Weather API (Open-Meteo forecast)
- Tool results included in final output

**Meaning:** Ground the AI response in real data and handle real-world failures (timeouts, missing data).

---

### Step 6 – Itinerary Generation

- LLM generates daily plan using structured input + weather summary
- Output validated and normalized

**Meaning:** Separate “creative generation” from data retrieval and control logic, and validate outputs like in production.

---

### Step 7 – Audit Logging

- Each request gets a UUID
- Execution time measured
- Tool calls logged
- Success and error cases recorded
- Logs stored in JSONL format in `data/audit_log.jsonl`

**Meaning:** Traceability and governance (debugging, accountability, reproducibility of decisions).

---

### Step 8 – Monitoring and Metrics

Prometheus metrics added:

- Total requests
- Successful requests
- Failed requests
- Request latency
- LLM latency
- Tool latency

Exposed via:

- `GET /metrics`

**Meaning:** Observability for production systems (performance tracking, error detection, later dashboards/autoscaling).

---

### Step 9 – Docker Containerization

- Created `Dockerfile`
- Created `.dockerignore`
- Built Docker image
- Verified API runs inside container

**Meaning:** Reproducibility and portability (the same application runs consistently on any machine with Docker).

---

## Running the Project

### Option 1 – Local Development

Start Ollama:

```bash
ollama run llama3.2
```

Create environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start API:

```bash
uvicorn app.main:app --reload
```

Open:

- http://127.0.0.1:8000/docs

---

### Option 2 – Docker (Recommended)

Build image:

```bash
docker build -t vacation-agent-api:0.1 .
```

Run container (Linux):

```bash
docker run --rm --network host vacation-agent-api:0.1
```

Open:

- http://127.0.0.1:8000/docs

---

## Available Endpoints

- `POST /v1/plan` – Generate vacation plan
- `GET /healthz` – Liveness check
- `GET /readyz` – Readiness check
- `GET /metrics` – Prometheus metrics
- `GET /docs` – Swagger UI

---

## Next Steps (Planned)

- Kubernetes deployment (Deployment/Service/Ingress)
- Helm chart for reproducible K8s installs
- Autoscaling (HPA)
- CI/CD pipeline (GitHub Actions)
- Security (secrets, scanning)

---

