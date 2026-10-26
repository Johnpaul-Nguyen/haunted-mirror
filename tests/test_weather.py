import weather

GEO = {"results": [
    {"name": "Norman", "latitude": 35.2, "longitude": -97.4, "admin1": "Oklahoma", "country_code": "US", "country": "United States"},
]}
GEO_AMBIGUOUS = {"results": [
    {"name": "Paris", "latitude": 48.8, "longitude": 2.3, "admin1": "Ile-de-France", "country_code": "FR", "country": "France"},
    {"name": "Paris", "latitude": 33.6, "longitude": -95.5, "admin1": "Texas", "country_code": "US", "country": "United States"},
]}
FORECAST = {
    "current": {"temperature_2m": 48.4, "weather_code": 61, "wind_speed_10m": 22.0},
    "daily": {"temperature_2m_max": [55.1], "temperature_2m_min": [39.9], "precipitation_probability_max": [70]},
}


def fake_fetch(responses):
    calls = []

    def fetch(url):
        calls.append(url)
        for key, value in responses.items():
            if key in url:
                return value
        raise AssertionError(f"unexpected url {url}")

    fetch.calls = calls
    return fetch


def test_describe_known_and_unknown_codes():
    assert weather.describe(0) == "clear sky"
    assert weather.describe(61) == "light rain"
    assert weather.describe(999) == "strange skies"


def test_geocode_uses_city_name_before_comma():
    fetch = fake_fetch({"geocoding": GEO})
    place = weather.geocode("Norman, OK", fetch)
    assert place == {"name": "Norman", "lat": 35.2, "lon": -97.4}
    assert "name=Norman&" in fetch.calls[0]


def test_geocode_prefers_region_hint():
    place = weather.geocode("Paris, TX", fake_fetch({"geocoding": GEO_AMBIGUOUS}))
    assert place["lat"] == 33.6


def test_geocode_no_results_returns_none():
    assert weather.geocode("Nowhere", fake_fetch({"geocoding": {}})) is None


def test_outfit_cold_wet_windy():
    advice = weather.outfit(now_f=40, high_f=45, rain_pct=70, wind_mph=25)
    assert "heavy coat" in advice
    assert "umbrella" in advice
    assert "wind" in " ".join(advice)


def test_outfit_mild_dry():
    assert weather.outfit(now_f=68, high_f=74, rain_pct=5, wind_mph=3) == ["light layers"]


def test_outfit_hot():
    advice = weather.outfit(now_f=92, high_f=98, rain_pct=0, wind_mph=5)
    assert "water" in " ".join(advice)


def test_get_weather_full_report():
    report = weather.Weather("Norman, OK", fake_fetch({"geocoding": GEO, "forecast": FORECAST})).get()
    assert report["city"] == "Norman"
    assert report["now_f"] == 48
    assert report["high_f"] == 55 and report["low_f"] == 40
    assert report["rain_pct"] == 70
    assert report["sky"] == "light rain"
    assert "umbrella" in report["advice"]


def test_get_weather_caches():
    fetch = fake_fetch({"geocoding": GEO, "forecast": FORECAST})
    w = weather.Weather("Norman, OK", fetch)
    w.get()
    w.get()
    assert len(fetch.calls) == 2  # one geocode + one forecast, second call cached


def test_get_weather_failure_returns_none():
    def broken(url):
        raise OSError("offline")

    assert weather.Weather("Norman, OK", broken).get() is None


def test_no_city_returns_none():
    assert weather.Weather("", fake_fetch({})).get() is None
