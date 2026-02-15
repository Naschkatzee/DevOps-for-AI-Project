# Vacation Agent -- DevOps for AI Project

This project implements a production-style AI agent service that takes a
free-text vacation request, parses it using an LLM, decides which tools
to call (weather, attractions), generates a structured itinerary, and
runs inside a fully containerized and Kubernetes-deployed environment
with CI/CD automation.

The goal of this project is to demonstrate **DevOps principles applied to AI systems**.

------------------------------------------------------------------------

## What the Service Does

The API receives a natural language request such as:

> "I want a 4-day trip in May to Barcelona, budget €800, I like culture
> and food, starting from Berlin."

The system then:

1. Parses the request using an LLM (Ollama) into structured JSON
2. Validates and normalizes the structured output using Pydantic schemas
3. Applies decision logic (if/else) to decide which tools to call (weather, attractions, etc.)
4. Calls external APIs (Open-Meteo geocoding + weather, and optionally Overpass for attractions)
5. Generates a day-by-day itinerary using the LLM (grounded in tool results)
6. Logs execution details (request ID, timings, tool usage, status) for traceability
7. Exposes Prometheus metrics for monitoring
8. Returns a structured JSON response
9. Persists request and result data in a SQLite database for traceability and auditing

The service is containerized with Docker and can be deployed to Kubernetes using Helm, 
with CI building and publishing container images to GitHub Container Registry (GHCR) via GitHub Actions.

------------------------------------------------------------------------

# Architecture

User → FastAPI → LLM (Ollama)\
                    ↘ Weather API (Open-Meteo)\
                    ↘ Attractions API\
                    ↘ SQLite (Persistence)\
                    ↘ Prometheus Metrics

------------------------------------------------------------------------

# Overview

The project started with creating a simple FastAPI service that exposes basic endpoints such as /healthz, /readyz, and /docs. This provided a clear API structure and allowed health checks, which are important for monitoring and CI pipelines. Input validation was implemented using Pydantic models to make sure that user requests are structured correctly and that invalid data is rejected early.

Next, a local LLM (via Ollama) was integrated to transform natural language travel requests into structured JSON data. The output of the LLM was validated against predefined schemas to ensure consistency and reliability. Decision logic was then added using explicit if/else rules to determine which external tools (e.g., weather or attractions APIs) should be called. This ensured that the overall system flow remains predictable and not fully controlled by the AI model.

External APIs were integrated to enrich the generated travel plans with real weather data and attractions information. Based on the structured input and tool results, the LLM generated a daily itinerary. Additional validation and normalization steps were included to handle incorrect or unexpected model outputs.

Audit logging was implemented to store request details in a JSONL log file and in a SQLite database. This improves traceability and helps with debugging and analysis. Prometheus metrics were added to monitor request counts, error rates, latency, and tool usage. This improves observability and allows performance analysis.

The application was containerized using Docker to ensure reproducible builds and consistent runtime environments. Kubernetes deployment was implemented using Helm charts, following Infrastructure as Code principles. Horizontal Pod Autoscaling (HPA) was configured to automatically scale the application based on CPU usage.

A CI/CD pipeline was created using GitHub Actions. The pipeline checks the code, installs dependencies, builds a Docker image, and pushes it to GitHub Container Registry (GHCR). This ensures automated and reproducible builds. Finally, SQLite persistence was added to store structured request data in a database, enabling long-term storage and analysis of generated travel plans.

------------------------------------------------------------------------

# How to Run the Project

## Open the Project Folder

``` bash
cd ~/vacation-agent
ls
```

Expected folders:

-   app/
-   requirements.txt
-   Dockerfile
-   helm/
-   .github/
-   scripts/

------------------------------------------------------------------------

## Check Required Ports (Common Issue)

### Port 8000 (FastAPI)

``` bash
ss -ltnp | grep ':8000' || echo "8000 is free"
```

If occupied:

``` bash
sudo fuser -k 8000/tcp
```

### Port 11434 (Ollama)

``` bash
ss -ltnp | grep ':11434' || echo "11434 is free"
```

If LISTEN appears, Ollama is already running (this is fine).

------------------------------------------------------------------------

## Verify Ollama (LLM Dependency)

### Check if Ollama is reachable

``` bash
curl -s http://127.0.0.1:11434/api/tags | head
```

If no connection:

``` bash
ollama serve
```

### Ensure model exists

``` bash
ollama list | grep -E 'llama3|llama3.2' || echo "model not found"
```

If missing:

``` bash
ollama pull llama3.2
```

------------------------------------------------------------------------

## Local Development (Python)

### Create an environment (if it already exists proceed to the "Activate venv")

Inside the project root (~/vacation-agent), run:

``` bash
python3 -m venv .venv
```

### Activate venv

``` bash
source .venv/bin/activate
```

### Install dependencies

``` bash
pip install -r requirements.txt
```

### Start API

``` bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

http://127.0.0.1:8000/docs



------------------------------------------------------------------------    
    
## Health Check

``` bash
curl -s http://127.0.0.1:8000/healthz
```


Expected:

{"status":"ok"}


------------------------------------------------------------------------

## Docker Usage
(Precondition: the local uvicorn is not running)

## Build Image

``` bash
docker build -t vacation-agent-api:0.1 .
```

## Run Container

``` bash
docker run --rm --network=host \
  -e OLLAMA_URL=http://127.0.0.1:11434/api/generate \
  vacation-agent-api:0.1
```

------------------------------------------------------------------------

## Kubernetes Deployment (k3d)

Create cluster:

``` bash
k3d cluster create devops-ai
```

=> A context named "k3d-devops-ai" should be created

If multiple clusters are available, do the following safety step to ensure 
the correct cluster is selected before proceeding.:

``` bash
kubectl config use-context k3d-devops-ai
```


Deploy via Helm:

``` bash
helm upgrade --install vacation-agent ./helm/vacation-agent
```

Check:

``` bash
kubectl get pods
kubectl get svc
kubectl get hpa
```

------------------------------------------------------------------------

## CI/CD Deployment


On push to `main`:

-   Build Docker image
-   Push to GHCR
-   Tag with commit SHA

------------------------------------------------------------------------

## Local Kubernetes Deployment (k3d)

Build locally:

``` bash
./scripts/deploy-local-build.sh devops-ai
```

Using GHCR image:

``` bash
./scripts/deploy-local-ghcr.sh devops-ai
```

------------------------------------------------------------------------


## Verify Deployment

``` bash
kubectl get pods
kubectl get svc
kubectl get ingress
kubectl get hpa
kubectl top pods
```

------------------------------------------------------------------------

## Metrics

``` bash
curl http://127.0.0.1:8000/metrics
```

------------------------------------------------------------------------

## Database Inspection

``` bash
sqlite3 data/vacation_agent.db
SELECT COUNT(*) FROM plans;
```

Should return ≥ 1.

------------------------------------------------------------------------