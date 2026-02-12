import json

from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Vacation Agent API", version="0.3.0")

# Local LLM (free) via Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
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


@app.post("/v1/plan", response_model=PlanResponse)
def create_plan(req: PlanRequest):
    parsed = parse_query_with_llm(req.query)
    decision = decide_actions(parsed)

    
    weather = None
    if "get_weather" in decision.actions and parsed.destination:
        weather = get_weather_daily(parsed.destination)

    # Placeholder itinerary (Step 3: we only prove parsing works; planning comes next)
    days = parsed.days or 4
    itinerary = [f"Day {i}: (placeholder) Planned activities" for i in range(1, days + 1)]

    return PlanResponse(
        request_id="demo-001",
        summary="Parsed your request into structured data. Next step will use tools + generate a real itinerary.",
        itinerary=itinerary,
        parsed=parsed,
        decision=decision,
        weather=weather,

    )
