"""Comprehensive unit test suite for MausamSahayak (Swati's Bot).

Runs 100% standalone with mocked external services (no live Telegram, backend, or SMS required).
Tests bilingual intents, conversational logic, risk formatting, safety rules, mock API scenarios,
and alert notification planning.
"""
import sys
from pathlib import Path

# Add project roots to sys.path so test runs cleanly from any working directory
root_dir = Path(__file__).resolve().parent.parent
parent_dir = root_dir.parent
for p in (str(parent_dir), str(root_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

import unittest

try:
    from swati_bot import alerts, formatters, i18n, intents, sms
    from swati_bot.api_client import ApiClient, ApiError
    from swati_bot.logic import BotLogic
    from swati_bot.store import Store
except ImportError:
    import alerts, formatters, i18n, intents, sms
    from api_client import ApiClient, ApiError
    from logic import BotLogic
    from store import Store



class TestIntentsAndLanguage(unittest.TestCase):
    """Test bilingual intent matching and query language detection."""

    def test_intent_detection(self):
        cases = {
            "what is the weather today": "weather",
            "aaj ka mausam": "weather",
            "weather please": "weather",
            "tomorrow weather": "forecast",
            "kal baarish hogi kya": "forecast",
            "kal ka mausam": "forecast",
            "barish kab hogi": "forecast",
            "khet ka haal batao": "sensors",
            "mere khet ki sthiti": "sensors",
            "soil moisture and water level": "sensors",
            "flood risk kya hai": "flood",
            "baadh aayegi kya": "flood",
            "heat wave risk": "heat",
            "loo chal rahi hai kya": "heat",
            "crop advice": "crop",
            "kaunsi fasal boyein": "crop",
            "fasal salah": "crop",
            "subscribe": "subscribe",
            "alert chalu karo": "subscribe",
            "unsubscribe": "unsubscribe",
            "alert band": "unsubscribe",
            "menu": "menu",
            "help me": "help",
            "madad chahiye": "help",
            "namaste": "greeting",
            "hello": "greeting",
            "random unmapped string": None,
            "": None,
        }
        for text, expected in cases.items():
            result = intents.detect_intent(text)
            self.assertEqual(result, expected, f"Failed matching intent for: '{text}' (got {result})")

    def test_language_detection(self):
        self.assertEqual(intents.detect_language("आज मौसम कैसा है"), "hi")
        self.assertEqual(intents.detect_language("kal baarish hogi kya"), "hi")
        self.assertEqual(intents.detect_language("mere khet ka haal"), "hi")
        self.assertEqual(intents.detect_language("What is the weather today?"), "en")
        self.assertEqual(intents.detect_language("give me crop advice"), "en")


class TestI18nAndSafetyRules(unittest.TestCase):
    """Verify linguistic symmetry and strict safety guidelines."""

    def test_translation_keys_symmetry(self):
        # All UI text keys must exist in both languages
        self.assertEqual(set(i18n.TEXT["en"]), set(i18n.TEXT["hi"]))
        # All reason codes must exist in both languages
        self.assertEqual(set(i18n.REASONS["en"]), set(i18n.REASONS["hi"]))
        # All crop codes must exist in both languages
        self.assertEqual(set(i18n.CROP_REASONS["en"]), set(i18n.CROP_REASONS["hi"]))
        # Flood and heat advice must cover all 5 alert levels
        levels = {"GREEN", "UNKNOWN", "YELLOW", "ORANGE", "RED"}
        for adv in (i18n.FLOOD_ADVICE, i18n.HEAT_ADVICE):
            self.assertEqual(set(adv["en"].keys()), levels)
            self.assertEqual(set(adv["hi"].keys()), levels)

    def test_unknown_risk_is_never_labeled_safe(self):
        """Rule: UNKNOWN risk must never be treated as SAFE."""
        for lang in ("en", "hi"):
            flood_unknown = i18n.FLOOD_ADVICE[lang]["UNKNOWN"]
            heat_unknown = i18n.HEAT_ADVICE[lang]["UNKNOWN"]

            # Must explicitly warn that status cannot be confirmed / is not safe
            if lang == "en":
                self.assertIn("NOT", flood_unknown)
                self.assertNotIn("safe.", flood_unknown.replace("does NOT mean it is safe.", ""))
            else:
                self.assertIn("सुरक्षित", flood_unknown)
                self.assertIn("नहीं", flood_unknown)

    def test_red_alert_mentions_authorities_and_helplines(self):
        """Rule: Critical RED flood advisories must state official emergency helplines."""
        for lang in ("en", "hi"):
            red_text = i18n.FLOOD_ADVICE[lang]["RED"]
            self.assertIn("112", red_text)
            self.assertIn("1078", red_text)
            if lang == "en":
                self.assertIn("advisory", red_text.lower())
            else:
                self.assertIn("परामर्श", red_text)


class TestConversationFlow(unittest.TestCase):
    """Simulate conversational flows in mock and error conditions."""

    def setUp(self):
        self.store = Store(":memory:")
        self.api = ApiClient(mock=True, demo_scenario="normal")
        self.logic = BotLogic(self.api, self.store)

    def tearDown(self):
        self.store.close()

    def test_english_flow(self):
        cid = 101
        # 1. /start
        r_start = self.logic.start(cid)
        self.assertTrue(r_start.ask_language)

        # 2. Choose English
        r_lang = self.logic.set_language(cid, "en")
        self.assertTrue(r_lang.ask_location)

        # 3. Share Location
        r_loc = self.logic.set_location(cid, 28.40, 77.31)
        self.assertIn("Kishanpur", r_loc.text)

        # 4. Ask Weather
        r_weather = self.logic.handle_text(cid, "what is the weather today")
        self.assertIn("Temperature", r_weather.text)
        self.assertIn("Humidity", r_weather.text)
        self.assertIn("Flood:", r_weather.text)

        # 5. Ask Field Sensors
        r_sensors = self.logic.handle_text(cid, "field sensors")
        self.assertIn("Soil Moisture", r_sensors.text)
        self.assertIn("Water Level", r_sensors.text)

        # 6. Ask Forecast
        r_forecast = self.logic.handle_text(cid, "weather forecast")
        self.assertIn("Forecast", r_forecast.text)

        # 7. Ask Crop Advice
        r_crop_prompt = self.logic.handle_text(cid, "crop advice")
        self.assertTrue(r_crop_prompt.ask_irrigation)
        r_crop_res = self.logic.crop(cid, irrigated=True)
        self.assertIn("Wheat", r_crop_res.text)
        self.assertIn("Crop suggestions", r_crop_res.text)
        self.assertIn("KVK", r_crop_res.text)

        # 8. Subscribe
        r_sub = self.logic.handle_text(cid, "subscribe")
        self.assertIn("alerts", r_sub.text.lower())

    def test_hindi_flow(self):
        cid = 102
        self.logic.set_language(cid, "hi")
        self.logic.set_location(cid, 28.40, 77.31)

        # 1. Weather in Hindi
        r_weather = self.logic.handle_text(cid, "आज मौसम कैसा है")
        self.assertIn("तापमान", r_weather.text)
        self.assertIn("नमी", r_weather.text)

        # 2. Sensors in Hindi ("khet ka haal")
        r_sensors = self.logic.handle_text(cid, "मेरे खेत का हाल बताओ")
        self.assertIn("मिट्टी की नमी", r_sensors.text)
        self.assertIn("जलस्तर", r_sensors.text)

        # 3. Forecast in Hindi
        r_forecast = self.logic.handle_text(cid, "कल बारिश होगी क्या")
        self.assertIn("पूर्वानुमान", r_forecast.text)

        # 4. Crop advice in Hindi
        r_crop = self.logic.crop(cid, irrigated=False, lang="hi")
        self.assertIn("फ़सल सुझाव", r_crop.text)
        self.assertIn("गेहूँ", r_crop.text)

    def test_no_location_prompts_user(self):
        cid = 103
        r = self.logic.current(cid)
        self.assertTrue(r.ask_location)

    def test_far_location_is_rejected(self):
        cid = 104
        self.logic.set_language(cid, "en")
        # Location in Mumbai (far from Haryana station > 50km)
        r_loc = self.logic.set_location(cid, 19.07, 72.87)
        self.assertIn("too far", r_loc.text)
        # Verify bot does not display local data for far location
        r_now = self.logic.current(cid)
        self.assertTrue(r_now.ask_location)

    def test_graceful_backend_down_handling(self):
        api_down = ApiClient(mock=True, demo_scenario="backend_down")
        logic_down = BotLogic(api_down, self.store)
        cid = 105
        logic_down.set_language(cid, "en")
        # Should gracefully return error message without throwing exception
        r = logic_down.set_location(cid, 28.40, 77.31)
        self.assertIn("cannot reach", r.text.lower())


class TestAlertsAndSMS(unittest.TestCase):
    """Test priority thresholds, deduplication, and SMS fallback."""

    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def test_should_notify_rules(self):
        # Flood escalation
        self.assertTrue(alerts.should_notify({"kind": "flood", "level": 2, "previous_level": 0}))
        # Sensor offline (escalates to UNKNOWN = level 1)
        self.assertTrue(alerts.should_notify({"kind": "flood", "level": 1, "previous_level": 0}))
        # Normalization from UNKNOWN to GREEN should not trigger emergency alert
        self.assertFalse(alerts.should_notify({"kind": "flood", "level": 0, "previous_level": 1}))
        # Dropping from severe RED to YELLOW informs farmers
        self.assertTrue(alerts.should_notify({"kind": "flood", "level": 2, "previous_level": 4}))
        # Minor heat YELLOW is not pushed
        self.assertFalse(alerts.should_notify({"kind": "heat", "level": 2, "previous_level": 0}))
        # Severe heat ORANGE/RED is pushed
        self.assertTrue(alerts.should_notify({"kind": "heat", "level": 3, "previous_level": 0}))

    def test_red_alert_dispatches_sms(self):
        cid = 201
        self.store.upsert_user(cid, lang="en", node_id="FIELD_01", node_name="Kishanpur",
                               subscribed=1, phone="+919876543210")

        red_alert = [{
            "id": 1,
            "node_id": "FIELD_01",
            "kind": "flood",
            "level": 4,
            "previous_level": 2,
            "level_name": "RED",
            "reasons": [{"code": "level_above_danger", "params": {"level_cm": 182, "danger_cm": 160}}]
        }]

        plans = alerts.plan_notifications(self.store, red_alert, self.store.node_names())
        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan.chat_id, cid)
        self.assertEqual(plan.sms_to, "+919876543210")
        self.assertIn("FLOOD ALERT", plan.sms_text)
        self.assertIn("Emergency 112", plan.sms_text)

    def test_phone_validation(self):
        self.assertTrue(sms.valid_phone("+919876543210"))
        self.assertTrue(sms.valid_phone("+918123456789"))
        self.assertFalse(sms.valid_phone("9876543210"))       # Missing country code
        self.assertFalse(sms.valid_phone("+911234567890"))     # Invalid starting digit
        self.assertFalse(sms.valid_phone("+9198765432"))       # Too short
        self.assertFalse(sms.valid_phone(""))
        self.assertFalse(sms.valid_phone(None))

    def test_dryrun_sms_sender(self):
        sender = sms.DryRunSender()
        ok = sender.send("+919876543210", "Flood alert test")
        self.assertTrue(ok)
        self.assertEqual(len(sender.sent), 1)
        self.assertEqual(sender.sent[0][0], "+919876543210")


class TestStaleSensorAndDemoScenarios(unittest.TestCase):
    """Test viva demonstration scenarios: stale sensor, red alert, normal."""

    def test_stale_sensor_scenario(self):
        api = ApiClient(mock=True, demo_scenario="stale_sensor")
        risk_data = api.risk("FIELD_01")
        self.assertTrue(risk_data["flood"]["stale"])
        self.assertEqual(risk_data["flood"]["level_name"], "UNKNOWN")

        formatted = formatters.format_risk("en", risk_data, "Kishanpur", 1.2)
        self.assertIn("unknown", formatted.lower())
        self.assertIn("NOT", formatted)

    def test_red_alert_scenario(self):
        api = ApiClient(mock=True, demo_scenario="red_alert")
        risk_data = api.risk("FIELD_01")
        self.assertEqual(risk_data["flood"]["level_name"], "RED")
        formatted = formatters.format_current("hi", risk_data, "किशनपुर", 1.2)
        self.assertIn("🔴", formatted)


if __name__ == "__main__":
    unittest.main()
