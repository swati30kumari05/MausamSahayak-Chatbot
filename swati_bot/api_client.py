"""Client for Manas's REST API and Offline Mock Provider (Swati's Bot).

Centralized module for:
1. Real HTTP calls to the backend REST API with timeouts and error handling.
2. High-fidelity Mock Mode (MOCK_API=true) allowing independent testing and viva demonstration
   without requiring running hardware or backend servers.
"""
import logging
import requests

log = logging.getLogger("api_client")


class ApiError(Exception):
    """Custom exception for API failures (timeout, network, 4xx/5xx, malformed JSON)."""
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class ApiClient:
    def __init__(self, base_url="http://localhost:8000", session=requests, timeout=10, mock=False, demo_scenario="normal"):
        self.base = base_url.rstrip("/") if base_url else "http://localhost:8000"
        self.s = session
        self.timeout = timeout
        self.mock = mock
        self.demo_scenario = demo_scenario.lower()

    def _get(self, path, **params):
        if self.mock:
            return self._mock_get(path, **params)

        try:
            r = self.s.get(self.base + path, params=params, timeout=self.timeout)
        except Exception as e:
            # Network issues, DNS failures, connection refused, timeouts
            log.warning("HTTP GET failed on %s: %s", path, e)
            raise ApiError(f"Network error: {e}") from e

        if r.status_code >= 500:
            raise ApiError(f"Server error {r.status_code}", r.status_code)

        try:
            body = r.json()
        except Exception as e:
            raise ApiError("Malformed JSON response from backend", r.status_code) from e

        if r.status_code >= 400:
            error_msg = body.get("error") if isinstance(body, dict) else f"Error {r.status_code}"
            raise ApiError(error_msg or "Unknown API error", r.status_code)

        return body

    # ----------------------------------------------------------- Public Methods
    def nearest(self, lat: float, lon: float) -> dict:
        """Find the nearest IoT monitoring station for the given coordinates."""
        return self._get("/api/nearest", lat=lat, lon=lon)

    def risk(self, node_id: str) -> dict:
        """Fetch current risk analysis and sensor readings for a field station."""
        return self._get(f"/api/nodes/{node_id}/risk")

    def crop_advice(self, lat: float, lon: float, irrigated: bool = False) -> dict:
        """Get agricultural crop recommendations for the region and irrigation type."""
        return self._get("/api/crop-advice", lat=lat, lon=lon, irrigated="1" if irrigated else "0")

    def forecast(self, lat: float, lon: float) -> dict:
        """Get 24h-48h weather forecast for the area."""
        return self._get("/api/weather/forecast", lat=lat, lon=lon)

    def sensors_latest(self, node_id: str) -> dict:
        """Fetch the latest raw environmental sensor readings."""
        return self._get(f"/api/sensors/latest", node_id=node_id)

    def alerts(self, since_id: int = 0) -> list:
        """Fetch active alerts since the specified alert ID."""
        res = self._get("/api/alerts", since_id=since_id)
        if isinstance(res, dict) and "alerts" in res:
            return res["alerts"]
        return res if isinstance(res, list) else []

    # ------------------------------------------------------------- Mock Engine
    def _mock_get(self, path: str, **params):
        """Generates realistic agricultural IoT data for development and viva testing."""
        # Simulated scenario: backend is down
        if self.demo_scenario == "backend_down":
            raise ApiError("Connection refused by agricultural monitoring server (Demo)", status=503)

        # 1. Nearest Station Lookup
        if path == "/api/nearest":
            lat = float(params.get("lat", 28.40))
            lon = float(params.get("lon", 77.31))
            # Test coordinate rejection if location is very far (e.g., > 50km away)
            ref_lat, ref_lon = 28.40, 77.31
            approx_km = (((lat - ref_lat) ** 2 + (lon - ref_lon) ** 2) ** 0.5) * 111.0
            within_range = approx_km <= 50.0

            return {
                "within_range": within_range,
                "distance_km": round(max(0.5, approx_km), 1),
                "node": {
                    "node_id": "FIELD_01",
                    "name": "Kishanpur Field Station",
                    "district": "Faridabad",
                    "latitude": 28.40,
                    "longitude": 77.31,
                }
            }

        # 2. Risk & Live Readings
        if "/risk" in path:
            return self._mock_risk_data()

        # 3. Crop Recommendations
        if path == "/api/crop-advice":
            irrigated = str(params.get("irrigated", "0")) in ("1", "true", "True")
            return {
                "season": "rabi",
                "irrigated": irrigated,
                "recommendations": [
                    {
                        "name_en": "Wheat (HD-2967 / Kalyan Sona)",
                        "name_hi": "गेहूँ (एच.डी.-2967 / कल्याण सोना)",
                        "score": 0.92 if irrigated else 0.65,
                        "reasons": [
                            {"code": "temp_ok", "params": {"temp": 24}},
                            {"code": "rain_ok" if irrigated else "rain_low", "params": {"rain": 45}}
                        ]
                    },
                    {
                        "name_en": "Mustard (Pusa Bold)",
                        "name_hi": "सरसों (पूसा बोल्ड)",
                        "score": 0.88,
                        "reasons": [
                            {"code": "temp_ok", "params": {"temp": 24}},
                            {"code": "rain_ok", "params": {"rain": 40}}
                        ]
                    },
                    {
                        "name_en": "Gram / Chickpea",
                        "name_hi": "चना (देसी)",
                        "score": 0.82,
                        "reasons": [
                            {"code": "temp_ok", "params": {"temp": 23}},
                            {"code": "rain_ok", "params": {"rain": 35}}
                        ]
                    }
                ]
            }

        # 4. Weather Forecast
        if path == "/api/weather/forecast":
            return {
                "location": "Kishanpur / Faridabad",
                "forecast_days": [
                    {
                        "day": "Today",
                        "day_hi": "आज",
                        "temp_max": 33.0,
                        "temp_min": 21.0,
                        "rain_chance_pct": 20,
                        "rain_expected_mm": 0.0,
                        "condition": "Partly Cloudy",
                        "condition_hi": "आंशिक बादल",
                    },
                    {
                        "day": "Tomorrow",
                        "day_hi": "कल",
                        "temp_max": 31.5,
                        "temp_min": 20.0,
                        "rain_chance_pct": 75 if self.demo_scenario == "red_alert" else 30,
                        "rain_expected_mm": 45.0 if self.demo_scenario == "red_alert" else 5.0,
                        "condition": "Heavy Rain" if self.demo_scenario == "red_alert" else "Passing Showers",
                        "condition_hi": "भारी बारिश" if self.demo_scenario == "red_alert" else "हल्की फुहारें",
                    }
                ]
            }

        # 5. Raw Sensors
        if path == "/api/sensors/latest":
            risk_data = self._mock_risk_data()
            return risk_data["reading"] or {}

        # 6. Active Alerts
        if path == "/api/alerts":
            since_id = int(params.get("since_id", 0))
            if self.demo_scenario == "red_alert" and since_id < 101:
                return {
                    "alerts": [
                        {
                            "id": 101,
                            "node_id": "FIELD_01",
                            "kind": "flood",
                            "level": 4,
                            "previous_level": 2,
                            "level_name": "RED",
                            "reasons": [
                                {
                                    "code": "level_above_danger",
                                    "params": {"level_cm": 182, "danger_cm": 160}
                                },
                                {
                                    "code": "flash_rise",
                                    "params": {"rise": 15}
                                }
                            ]
                        }
                    ]
                }
            return {"alerts": []}

        return {}

    def _mock_risk_data(self) -> dict:
        """Helper to create risk payload according to active demo scenario."""
        # Scenario: Stale Sensor Data (sensor offline > 60 min -> UNKNOWN status)
        if self.demo_scenario == "stale_sensor":
            return {
                "node_id": "FIELD_01",
                "minutes_since_last": 75,
                "reading": {
                    "temperature_c": 31.0,
                    "temperature": 31.0,
                    "humidity_pct": 60.0,
                    "humidity": 60.0,
                    "rain_24h_mm": 0.0,
                    "rainfall": 0.0,
                    "water_level_cm": 90.0,
                    "water_level": 0.9,
                    "soil_moisture_pct": 28.0,
                    "soil_moisture": 28.0,
                    "timestamp": "2026-10-27T10:45:00"
                },
                "flood": {
                    "level": 1,
                    "level_name": "UNKNOWN",
                    "stale": True,
                    "metrics": {"rain_24h_mm": 0.0},
                    "reasons": [{"code": "sensor_offline", "params": {"minutes": 75}}]
                },
                "heat": {
                    "level": 1,
                    "level_name": "UNKNOWN",
                    "stale": True,
                    "metrics": {},
                    "reasons": [{"code": "sensor_offline", "params": {"minutes": 75}}]
                }
            }

        # Scenario: Critical Red Flood Alert
        if self.demo_scenario == "red_alert":
            return {
                "node_id": "FIELD_01",
                "minutes_since_last": 2,
                "reading": {
                    "temperature_c": 26.5,
                    "temperature": 26.5,
                    "humidity_pct": 92.0,
                    "humidity": 92.0,
                    "rain_24h_mm": 110.0,
                    "rainfall": 110.0,
                    "water_level_cm": 182.0,
                    "water_level": 1.82,
                    "soil_moisture_pct": 88.0,
                    "soil_moisture": 88.0,
                    "timestamp": "2026-10-27T12:00:00"
                },
                "flood": {
                    "level": 4,
                    "level_name": "RED",
                    "stale": False,
                    "metrics": {"rain_24h_mm": 110.0, "rise_cm_per_h": 15.0},
                    "reasons": [
                        {"code": "level_above_danger", "params": {"level_cm": 182, "danger_cm": 160}},
                        {"code": "flash_rise", "params": {"rise": 15}}
                    ]
                },
                "heat": {
                    "level": 0,
                    "level_name": "GREEN",
                    "stale": False,
                    "metrics": {"feels_like_c": 27.0},
                    "reasons": []
                }
            }

        # Scenario: Normal Nominal Conditions (Default)
        return {
            "node_id": "FIELD_01",
            "minutes_since_last": 5,
            "reading": {
                "temperature_c": 32.4,
                "temperature": 32.4,
                "humidity_pct": 62.0,
                "humidity": 62.0,
                "rain_24h_mm": 2.5,
                "rainfall": 2.5,
                "water_level_cm": 95.0,
                "water_level": 0.95,
                "soil_moisture_pct": 33.0,
                "soil_moisture": 33.0,
                "timestamp": "2026-10-27T12:00:00"
            },
            "flood": {
                "level": 0,
                "level_name": "GREEN",
                "stale": False,
                "metrics": {"rain_24h_mm": 2.5, "rise_cm_per_h": 0.0},
                "reasons": []
            },
            "heat": {
                "level": 0,
                "level_name": "GREEN",
                "stale": False,
                "metrics": {"feels_like_c": 34.0},
                "reasons": []
            }
        }
