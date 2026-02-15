import json
import uuid

from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import time
from datetime import datetime, timezone
from pathlib import Path

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

from app.db import init_db, insert_plan

import os

app = FastAPI(title="Vacation Agent API", version="0.3.0")

REQUESTS_TOTAL = Counter(
    "vacation_agent_requests_total",
    "Total number of requests to /v1/plan",
)

REQUESTS_OK_TOTAL = Counter(
    "vacation_agent_requests_ok_total",
    "Total number of successful /v1/plan requests",
)

REQUESTS_ERROR_TOTAL = Counter(
    "vacation_agent_requests_error_total",
    "Total number of failed /v1/plan requests",
)

REQUEST_LATENCY = Histogram(
    "vacation_agent_request_latency_seconds",
    "Latency of /v1/plan in seconds",
)

LLM_LATENCY = Histogram(
    "vacation_agent_llm_latency_seconds",
    "Latency of LLM calls in seconds",
)

TOOL_LATENCY = Histogram(
    "vacation_agent_tool_latency_seconds",
    "Latency of external tool calls in seconds",
    ["tool"],
)

TOOL_CALLS_TOTAL = Counter(
    "vacation_agent_tool_calls_total",
    "Total tool calls",
    ["tool"],
)



DATA_DIR = Path("data")
AUDIT_LOG_PATH = DATA_DIR / "audit_log.jsonl"



# Local LLM (free) via Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = "llama3.2"

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


# ---- Step 2: define what input should look like ----
class PlanRequest(BaseModel):
    # Free text like: "I want a 4-day trip in May, budget €800, culture and food, from Berlin."
    query: str = Field(..., min_length=5, max_length=2000)


# ---- Step 3: define what the parsed (structured) data should look like ----
class ParsedTrip(BaseModel):
    days: Optional[int] = Field(default=None, ge=1, le=30)
    month: Optional[str | int] = None
    budget_eur: Optional[int] = Field(default=None, ge=0, le=20000)
    interests: list[str] = Field(default_factory=list)
    departure_city: Optional[str] = None
    destination: Optional[str] = None

# ---- Step 4: decision logic output ----
class Decision(BaseModel):
    actions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WeatherResult(BaseModel):
    city: str
    latitude: float
    longitude: float
    daily: dict  # we keep it simple for now (raw daily forecast)



# ---- API response ----
class PlanResponse(BaseModel):
    request_id: str
    summary: str
    itinerary: list[str]
    parsed: ParsedTrip
    decision: Decision
    weather: Optional[WeatherResult]=None


def normalize_llm_trip_dict(d: dict) -> dict:
    # days: "4" -> 4
    if isinstance(d.get("days"), str) and d["days"].strip().isdigit():
        d["days"] = int(d["days"].strip())

    # budget_eur: "800" -> 800
    if isinstance(d.get("budget_eur"), str) and d["budget_eur"].strip().isdigit():
        d["budget_eur"] = int(d["budget_eur"].strip())

    # interests: '["culture","food"]' -> ["culture","food"]
    if isinstance(d.get("interests"), str):
        s = d["interests"].strip()
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                d["interests"] = parsed
        except Exception:
            # If it's a plain string like "culture, food", split it
            if "," in s:
                d["interests"] = [x.strip() for x in s.split(",") if x.strip()]
            else:
                d["interests"] = [s] if s else []

    return d



def parse_query_with_llm(query: str) -> ParsedTrip:
    """
    Calls a local LLM (Ollama) to convert free-text into structured JSON.
    Returns ParsedTrip (validated). Raises HTTPException if anything fails.
    """
    prompt = f"""
You extract structured travel preferences from user text.
Return ONLY valid JSON (no markdown, no comments, no extra text) with exactly these keys:
days, month, budget_eur, interests, departure_city, destination

Rules:
- Use null if unknown.
- interests must be a JSON list of strings.
- No extra keys.

User request: {query}
""".strip()

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        r.raise_for_status()
        text = (r.json().get("response") or "").strip()
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=502,
            detail=(
                "Cannot reach Ollama at http://localhost:11434. "
                "Start it with: `ollama serve` (or run a model with `ollama run llama3.2`)."
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama call failed: {e}")

    # Validate + parse JSON into our schema (Step 3 core idea)
    try:
        raw_dict = json.loads(text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM returned non-JSON: {e}. Raw output: {text[:300]}")

    raw_dict = normalize_llm_trip_dict(raw_dict)

    try:
        return ParsedTrip.model_validate(raw_dict)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM output did not match schema even after normalization: {e}. Raw output: {text[:300]}",
        )

      
def generate_itinerary_with_llm(parsed: ParsedTrip, weather_summary: str) -> list[str]:
    days = parsed.days or 4
    interests = ", ".join(parsed.interests) if parsed.interests else "general sightseeing"

    prompt = f"""
You are a travel planner.
Return ONLY valid JSON: a list of {days} strings (one per day).
No markdown. No extra text.

Trip:
- Destination: {parsed.destination}
- Days: {days}
- Month: {parsed.month}
- Budget EUR: {parsed.budget_eur}
- Interests: {interests}
- Departure city: {parsed.departure_city}

Weather summary:
{weather_summary}

Rules:
- If rain is high on a day, plan more indoor activities.
- Include at least one food-related idea if interests include food.
- Include at least one culture-related idea if interests include culture.
- Keep each day concise.
""".strip()

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        text = (r.json().get("response") or "").strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama itinerary call failed: {e}")

    try:
        data = json.loads(text)

        # Case 1: correct format -> list of strings
        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            itinerary = data

        # Case 2: model returned {"day1": "...", "day2": "..."} -> convert to list
        elif isinstance(data, dict):
            # sort keys like day1, day2, day3...
            def day_key(k: str) -> int:
                digits = "".join(ch for ch in k if ch.isdigit())
                return int(digits) if digits.isdigit() else 999

            items = sorted(data.items(), key=lambda kv: day_key(kv[0]))
            itinerary = [v for _, v in items if isinstance(v, str)]

            if not itinerary:
                raise ValueError("Dict itinerary did not contain string values")

        else:
            raise ValueError("Itinerary must be a JSON list of strings or a day-key dict")

        # Ensure correct length (trim/pad)
        if len(itinerary) > days:
            itinerary = itinerary[:days]
        elif len(itinerary) < days:
            itinerary = itinerary + [f"Day {i+1}: Free exploration." for i in range(len(itinerary), days)]

        return itinerary

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned invalid itinerary JSON: {e}. Raw output: {text[:300]}",
        )



def decide_actions(parsed: ParsedTrip) -> Decision:
    actions: list[str] = []
    notes: list[str] = []

    # If user didn't specify a destination, we must choose/suggest one later
    if not parsed.destination:
        actions.append("need_destination")
        notes.append("Destination missing -> later we will suggest options.")

    # Weather is useful if we have a time hint (month) and a destination
    if parsed.month and (parsed.destination is not None):
        actions.append("get_weather")
        notes.append("Month present -> weather helps plan indoor/outdoor days.")

    # Attractions are useful if interests exist and we have a destination
    if parsed.interests and (parsed.destination is not None):
        actions.append("get_attractions")
        notes.append("Interests present -> fetch points of interest matching interests.")

    # If nothing triggered, still proceed with basic itinerary generation
    if not actions:
        actions.append("basic_plan")
        notes.append("No tool calls needed -> generate a basic plan.")

    return Decision(actions=actions, notes=notes)


def geocode_city(city: str) -> tuple[float, float]:
    try:
        r = requests.get(
            GEOCODE_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            raise HTTPException(status_code=502, detail=f"Geocoding returned no results for '{city}'")
        return results[0]["latitude"], results[0]["longitude"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Geocoding failed: {e}")


def get_weather_daily(city: str) -> WeatherResult:
    lat, lon = geocode_city(city)

    try:
        r = requests.get(
            WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        daily = data.get("daily") or {}
        return WeatherResult(city=city, latitude=lat, longitude=lon, daily=daily)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather API failed: {e}")


def summarize_weather(weather: WeatherResult, max_days: int = 4) -> str:
    daily = weather.daily or {}
    dates = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    rain = daily.get("precipitation_sum") or []

    lines = []
    for i in range(min(max_days, len(dates), len(tmax), len(tmin), len(rain))):
        lines.append(f"{dates[i]}: {tmin[i]}–{tmax[i]}°C, rain {rain[i]}mm")
    return " | ".join(lines) if lines else "No forecast available."


def write_audit_log(entry: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")



def timed_call(hist: Histogram, fn, *args, **kwargs):
    start = time.time()
    result = fn(*args, **kwargs)
    hist.observe(time.time() - start)
    return result




@app.get("/")
def root():
    return {"message": "Vacation Agent API is running"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    # Later we'll check dependencies here (DB, Redis, etc.)
    return {"status": "ready"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/v1/plan", response_model=PlanResponse)
def create_plan(req: PlanRequest):
    
    REQUESTS_TOTAL.inc()
    req_start = time.time()

    request_id = str(uuid.uuid4())
    started = time.time()

    # Store only a small preview for privacy (optional, but good practice)
    query_preview = req.query[:200]

    tool_calls: list[str] = []
    weather = None
    weather_summary = "Unknown"

    try:
        parsed = timed_call(LLM_LATENCY, parse_query_with_llm, req.query)
        decision = decide_actions(parsed)

        if "get_weather" in decision.actions and parsed.destination:
            TOOL_CALLS_TOTAL.labels("geocoding").inc()
            TOOL_CALLS_TOTAL.labels("weather").inc()
            tool_calls += ["geocoding", "weather"]

            weather = timed_call(TOOL_LATENCY.labels("weather"), get_weather_daily, parsed.destination)
            weather_summary = summarize_weather(weather, max_days=parsed.days or 4)


        itinerary = timed_call(LLM_LATENCY, generate_itinerary_with_llm, parsed, weather_summary)

        duration_ms = int((time.time() - started) * 1000)

        # ---- Step 7: write audit log (success) ----
        write_audit_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "status": "ok",
            "duration_ms": duration_ms,
            "query_preview": query_preview,
            "parsed": parsed.model_dump(),
            "decision": decision.model_dump(),
            "tool_calls": tool_calls,
            "has_weather": weather is not None,
        })


        REQUESTS_OK_TOTAL.inc()
        REQUEST_LATENCY.observe(time.time() - req_start)


        insert_plan(
    	    plan_id=request_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            query_preview=query_preview,
            parsed=parsed.model_dump(),
            decision=decision.model_dump(),
            weather=weather.model_dump() if weather is not None else None,
            itinerary=itinerary,
            status="ok",
            duration_ms=duration_ms,
       )




        return PlanResponse(
            request_id=request_id,
            summary="Generated itinerary using structured input and weather data.",
            itinerary=itinerary,
            parsed=parsed,
            decision=decision,
            weather=weather,
        )

    except HTTPException as e:
        duration_ms = int((time.time() - started) * 1000)

        # ---- Step 7: write audit log (controlled error) ----
        write_audit_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "status": "error",
            "duration_ms": duration_ms,
            "query_preview": query_preview,
            "error": {"status_code": e.status_code, "detail": e.detail},
        })
        REQUESTS_ERROR_TOTAL.inc()
        REQUEST_LATENCY.observe(time.time() - req_start)

        raise

    except Exception as e:
        duration_ms = int((time.time() - started) * 1000)

        # ---- Step 7: write audit log (unexpected error) ----
        write_audit_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "status": "error",
            "duration_ms": duration_ms,
            "query_preview": query_preview,
            "error": {"type": type(e).__name__, "message": str(e)},
        })
        REQUESTS_ERROR_TOTAL.inc()
        REQUEST_LATENCY.observe(time.time() - req_start)

        insert_plan(
            plan_id=request_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            query_preview=query_preview,
            parsed={},
            decision={},
            weather=None,
            itinerary=[],
            status="error",
            duration_ms=duration_ms,
        )


        raise HTTPException(status_code=500, detail="Internal server error")


@app.on_event("startup")
def _startup():
    init_db()
