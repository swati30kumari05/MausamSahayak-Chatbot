"""End-to-End integration test connecting Nishant's firmware simulator, Manas's Flask backend,
Parul's risk logic, and Swati's Telegram bot conversation logic (Swati's Bot).
"""
import os
import sys
from pathlib import Path
import tempfile
import unittest

# Ensure parent modules can be imported
root = Path(__file__).resolve().parent.parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

try:
    from manas_backend import db, ingest, service
    from manas_backend.api import create_app
    from manas_backend.config import Settings
    from nishant_firmware.simulator import scenarios
    MODULES_AVAILABLE = True
except (ImportError, PermissionError, OSError):
    MODULES_AVAILABLE = False

from swati_bot import alerts, formatters, i18n, intents, sms
from swati_bot.api_client import ApiClient, ApiError
from swati_bot.logic import BotLogic
from swati_bot.store import Store

NOW = 1_790_000_000


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._b = body

    def json(self):
        if isinstance(self._b, Exception):
            raise self._b
        return self._b


class FlaskSession:
    """Allows ApiClient to invoke Manas's live Flask app in-process."""
    def __init__(self, client):
        self.c = client

    def get(self, url, params=None, timeout=None):
        path = "/" + url.split("/", 3)[3]
        r = self.c.get(path, query_string=params)
        return FakeResp(r.status_code, r.json)


@unittest.skipUnless(MODULES_AVAILABLE, "Teammate modules (manas_backend, nishant_firmware) not in python path")
class TestFullTeamEndToEnd(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        path = os.path.join(self.d.name, "test_e2e.db")
        self.conn = db.connect(path)
        db.init_db(self.conn)

        # 1. Setup field monitoring nodes (Faridabad & River stations)
        service.add_node(self.conn, "n1", "Campus Station", 28.40, 77.31, "Faridabad", "Haryana", 450.0, NOW)
        service.add_node(self.conn, "n2", "River Bank Station", 28.42, 77.33, "Faridabad", "Haryana", 450.0, NOW)

        # 2. Ingest sensor readings from Nishant's simulator
        for r in scenarios.backfill("normal", "n1", NOW, seed=1):
            ingest.store_reading(self.conn, "n1", r, NOW)
        for r in scenarios.backfill("flood", "n2", NOW, seed=1):
            ingest.store_reading(self.conn, "n2", r, NOW)

        # 3. Spin up Manas's Flask Backend
        app = create_app(Settings(db_path=path, api_key="test_key"), forecast_fn=lambda a, b: {"next_24h_mm": 50.0}, clock=lambda: NOW)
        self.api = ApiClient("http://localhost:8000", session=FlaskSession(app.test_client()), mock=False)
        self.store = Store(":memory:")
        self.logic = BotLogic(self.api, self.store)

    def tearDown(self):
        self.conn.close()
        self.d.cleanup()
        self.store.close()

    def test_complete_integration_flow(self):
        cid = 999
        # Start and choose English
        self.logic.start(cid)
        self.logic.set_language(cid, "en")

        # Set Location near n1
        r_loc = self.logic.set_location(cid, 28.401, 77.311)
        self.assertIn("Campus", r_loc.text)

        # Ask weather -> gets live sensor data from Manas's backend
        r_weather = self.logic.handle_text(cid, "what is the weather today")
        self.assertIn("Temperature", r_weather.text)
        self.assertIn("Flood:", r_weather.text)

        # Ask crop advice -> gets Parul's crop recommendations through Manas's API
        r_crop = self.logic.crop(cid, irrigated=True)
        self.assertIn("Crop suggestions", r_crop.text)

        # Subscribe to alerts
        r_sub = self.logic.subscribe(cid)
        self.assertIn("Campus", r_sub.text)


if __name__ == "__main__":
    unittest.main()
