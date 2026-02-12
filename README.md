# DevOps for AI – Vacation Agent Service

A small AI agent web service that:
- accepts a vacation request via API
- parses the request into structured JSON using a local LLM (Ollama)
- (next) applies decision logic, calls tools (weather/attractions), and generates an itinerary

## Run locally

### 1) Start the local LLM (Ollama)
Install Ollama, then:
```bash
ollama run llama3.2
