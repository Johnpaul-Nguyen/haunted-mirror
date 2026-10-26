"""Local forecast and outfit advice from Open-Meteo (free, no key)."""

import json
import time
import urllib.parse
import urllib.request

CACHE_SECONDS = 30 * 60

SKIES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


US_STATES = dict(zip(
    "al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy dc".split(),
    ["alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida",
     "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
     "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana", "nebraska",
     "nevada", "new hampshire", "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio",
     "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", "texas",
     "utah", "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming", "district of columbia"],
))


def http_json(url):
    with urllib.request.urlopen(url, timeout=8) as resp:
        return json.load(resp)


def describe(code):
    return SKIES.get(code, "strange skies")


def geocode(city, fetch=http_json):
    """'Norman, OK' -> {'name', 'lat', 'lon'}. The part after the comma picks between matches."""
    name, _, hint = city.partition(",")
    name, hint = name.strip(), hint.strip().lower()
    hint = US_STATES.get(hint, hint)
    query = urllib.parse.urlencode({"name": name, "count": 10, "language": "en", "format": "json"})
    results = fetch(f"https://geocoding-api.open-meteo.com/v1/search?{query}").get("results") or []
    if not results:
        return None

    def matches(r):
        return hint and (
            str(r.get("admin1", "")).lower().startswith(hint)
            or str(r.get("country_code", "")).lower() == hint
            or str(r.get("country", "")).lower().startswith(hint)
        )

    best = next((r for r in results if matches(r)), results[0])
    return {"name": best["name"], "lat": best["latitude"], "lon": best["longitude"]}


def outfit(now_f, high_f, rain_pct, wind_mph):
    advice = []
    coldest = min(now_f, high_f)
    if coldest < 50:
        advice.append("heavy coat")
    elif coldest < 62:
        advice.append("jacket")
    elif high_f >= 88:
        advice.append("light clothes and water")
    else:
        advice.append("light layers")
    if rain_pct >= 40:
        advice.append("umbrella")
    if wind_mph >= 18:
        advice.append("something the wind can't steal")
    return advice


class Weather:
    def __init__(self, city, fetch=http_json):
        self.city = (city or "").strip()
        self.fetch = fetch
        self._place = None
        self._report = None
        self._at = 0.0

    def get(self):
        if not self.city:
            return None
        if self._report and time.time() - self._at < CACHE_SECONDS:
            return self._report
        try:
            self._place = self._place or geocode(self.city, self.fetch)
            if not self._place:
                return None
            query = urllib.parse.urlencode({
                "latitude": self._place["lat"],
                "longitude": self._place["lon"],
                "current": "temperature_2m,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
                "forecast_days": 1,
            })
            data = self.fetch(f"https://api.open-meteo.com/v1/forecast?{query}")
            now, day = data["current"], data["daily"]
            report = {
                "city": self._place["name"],
                "now_f": round(now["temperature_2m"]),
                "high_f": round(day["temperature_2m_max"][0]),
                "low_f": round(day["temperature_2m_min"][0]),
                "rain_pct": int(day["precipitation_probability_max"][0] or 0),
                "wind_mph": round(now["wind_speed_10m"]),
                "sky": describe(now["weather_code"]),
            }
            report["advice"] = outfit(report["now_f"], report["high_f"], report["rain_pct"], report["wind_mph"])
        except (OSError, KeyError, IndexError, TypeError, ValueError) as err:
            print(f"[weather] failed: {err}")
            return None
        self._report, self._at = report, time.time()
        return report
