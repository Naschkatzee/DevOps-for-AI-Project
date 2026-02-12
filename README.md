# DevOps for AI – Vacation Agent Service

## Project Description

This project was developed for the university course **"DevOps for
AI"**.

It implements a simple AI-powered vacation planning service and focuses
on how to integrate a Large Language Model (LLM) into a structured,
controllable, and reproducible backend system.

The main goal is not only to use AI, but to demonstrate how AI systems
can be:

-   Controlled with deterministic logic
-   Validated and monitored
-   Integrated with external tools
-   Managed in a reproducible development environment

------------------------------------------------------------------------

## What the Service Does

The service receives a natural language vacation request and:

1.  Extracts structured data using a local LLM (Ollama)
2.  Validates the extracted data using schemas (Pydantic)
3.  Applies deterministic decision logic
4.  Calls an external Weather API (Open-Meteo)
5.  Generates a day-by-day itinerary
6.  Returns a structured JSON response

The system combines probabilistic AI (LLM) with deterministic backend
logic.

------------------------------------------------------------------------

## Example API Call

POST `/v1/plan`

``` json
{
  "request": "I want a 4-day trip in May to Barcelona, budget €800, I like culture and food, starting from Berlin."
}
```

Example Response (simplified):

``` json
{
  "request_id": "uuid",
  "parsed_data": { ... },
  "weather": { ... },
  "itinerary": [
    "Day 1: ...",
    "Day 2: ..."
  ]
}
```

------------------------------------------------------------------------

## Architecture

The system is built using:

-   FastAPI -- REST API layer
-   Ollama -- Local LLM
-   Pydantic -- Schema validation
-   Open-Meteo API -- External tool integration
-   Deterministic control layer 

Processing flow:

User → API → LLM → Validation → Decision Logic → Weather API → Itinerary
→ JSON Response

------------------------------------------------------------------------

## DevOps Aspects

This project demonstrates DevOps concepts for AI systems:

-   Schema validation of LLM outputs
-   Deterministic control over AI behavior
-   External API integration
-   Health check endpoint (`/healthz`)
-   Reproducible local environment (venv + requirements.txt)
-   Version-controlled development
-   Clear separation between AI logic and backend logic


------------------------------------------------------------------------

## Running the Project Locally

### 1. Start Ollama

``` bash
ollama run llama3.2
```

### 2. Create Python Environment

``` bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start the API

``` bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open in browser:

http://127.0.0.1:8000/docs

------------------------------------------------------------------------

## Available Endpoints

-   POST `/v1/plan` -- Generate vacation plan
-   GET `/docs` -- Swagger UI
-   GET `/healthz` -- Health check

------------------------------------------------------------------------

## Future Extensions

-   Docker containerization
-   CI/CD pipeline (GitHub Actions)
-   Metrics endpoint (Prometheus)
-   Logging and monitoring
-   Deployment to Kubernetes
-   Secure secret management

------------------------------------------------------------------------

## Conclusion

This project shows how AI components can be integrated into a structured
backend system using DevOps principles. It demonstrates how to combine
LLM-based reasoning with deterministic software engineering practices to
build a reliable AI service.
