"""Turn API JSON data into farmer-friendly natural language responses (Swati's Bot).

Defensively formats sensor metrics, weather forecasts, risk assessments, crop suggestions,
and emergency alert advisories in Hindi or English.
"""
from . import i18n
from .i18n import CROP_REASONS, FLOOD_ADVICE, HEAT_ADVICE, LEVEL_EMOJI, LEVEL_NAME, REASONS, SEASON, t


def level_label(lang: str, level_name: str) -> str:
    lang = i18n.norm_lang(lang)
    emoji = LEVEL_EMOJI.get(level_name, "⚪")
    name = LEVEL_NAME.get(lang, {}).get(level_name, level_name)
    return f"{emoji} {name}"


def reason_text(lang: str, reason: dict) -> str:
    lang = i18n.norm_lang(lang)
    code = reason.get("code", "")
    params = dict(reason.get("params") or {})

    if code == "sensor_offline" and params.get("minutes") is None:
        code = "sensor_offline_none"

    tpl = REASONS[lang].get(code) or REASONS["en"].get(code)
    if tpl is None:
        return code.replace("_", " ")

    try:
        return tpl.format(**params)
    except (KeyError, IndexError, ValueError):
        return tpl


def _v(x, unit="", nd=1):
    if x is None:
        return "-"
    try:
        val = round(float(x), nd)
        # Format without trailing .0 if integer
        formatted = f"{int(val)}" if val == int(val) else f"{val}"
        return f"{formatted}{unit}"
    except (ValueError, TypeError):
        return str(x)


def _get_val(d: dict, *keys):
    """Safely extracts value from a dict trying multiple candidate keys."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def format_current(lang: str, risk: dict, node_name: str, distance_km: float) -> str:
    """Format current weather and risk overview for the farmer's station."""
    lang = i18n.norm_lang(lang)
    reading = risk.get("reading") or {}
    lines = [t(lang, "current_title", name=node_name, km=distance_km)]

    if not reading:
        lines.append(t(lang, "no_data_yet"))
    else:
        temp = _get_val(reading, "temperature_c", "temperature")
        hum = _get_val(reading, "humidity_pct", "humidity")
        water = _get_val(reading, "water_level_cm", "water_level")
        soil = _get_val(reading, "soil_moisture_pct", "soil_moisture")
        rain24 = _get_val(reading, "rain_24h_mm", "rainfall", "rain")

        flood_block = risk.get("flood") or {}
        flood_metrics = flood_block.get("metrics") or {}
        if rain24 is None:
            rain24 = flood_metrics.get("rain_24h_mm")

        lines += [
            f"{t(lang, 'temperature')}: {_v(temp, ' °C')}",
            f"{t(lang, 'humidity')}: {_v(hum, ' %', 0)}",
            f"{t(lang, 'rain24')}: {_v(rain24, ' mm')}",
            f"{t(lang, 'water')}: {_v(water, ' cm', 0)}",
            f"{t(lang, 'soil')}: {_v(soil, ' %', 0)}"
        ]

        age = risk.get("minutes_since_last")
        if age is not None:
            lines.append(t(lang, "updated", age=round(age)))

    # Stale sensor alert handling
    flood_info = risk.get("flood") or {}
    flood_stale = flood_info.get("stale", False)
    if flood_stale:
        age = risk.get("minutes_since_last")
        age_str = "?" if age is None else str(round(age))
        lines.append(t(lang, "stale_line", age=age_str))

    lines.append("")
    flood_lvl = flood_info.get("level_name", "UNKNOWN")
    lines.append(t(lang, "flood_line", emoji=LEVEL_EMOJI.get(flood_lvl, "⚪"),
                   label=LEVEL_NAME[lang].get(flood_lvl, flood_lvl)))

    heat_info = risk.get("heat") or {}
    if not heat_info.get("stale", False):
        heat_lvl = heat_info.get("level_name", "UNKNOWN")
        lines.append(t(lang, "heat_line", emoji=LEVEL_EMOJI.get(heat_lvl, "⚪"),
                       label=LEVEL_NAME[lang].get(heat_lvl, heat_lvl)))

    return "\n".join(lines)


def format_sensors(lang: str, reading: dict, node_name: str, distance_km: float, age_min: float | None = None) -> str:
    """Format dedicated field IoT sensor measurements (Nishant's hardware)."""
    lang = i18n.norm_lang(lang)
    lines = [t(lang, "sensors_title", name=node_name, km=distance_km)]

    if not reading:
        lines.append(t(lang, "no_data_yet"))
        return "\n".join(lines)

    temp = _get_val(reading, "temperature_c", "temperature")
    hum = _get_val(reading, "humidity_pct", "humidity")
    rain = _get_val(reading, "rain_24h_mm", "rainfall", "rain")
    water = _get_val(reading, "water_level_cm", "water_level")
    soil = _get_val(reading, "soil_moisture_pct", "soil_moisture")

    lines += [
        f"{t(lang, 'temperature')}: {_v(temp, ' °C')}",
        f"{t(lang, 'humidity')}: {_v(hum, ' %', 0)}",
        f"{t(lang, 'rainfall')}: {_v(rain, ' mm')}",
        f"{t(lang, 'soil_moisture')}: {_v(soil, ' %', 0)}",
        f"{t(lang, 'water_level')}: {_v(water, ' cm', 0)}"
    ]

    if age_min is not None:
        lines.append(t(lang, "updated", age=round(age_min)))

    return "\n".join(lines)


def format_forecast(lang: str, forecast_data: dict, node_name: str) -> str:
    """Format weather forecast data (Anil's external data)."""
    lang = i18n.norm_lang(lang)
    lines = [t(lang, "forecast_title", name=node_name), ""]

    days = forecast_data.get("forecast_days") or []
    if not days:
        lines.append("No forecast details available for the next 48 hours.")
        return "\n".join(lines)

    for d in days:
        day_label = d.get(f"day_{lang}") or d.get("day") or "Day"
        condition = d.get(f"condition_{lang}") or d.get("condition") or "Clear"
        max_t = _v(d.get("temp_max"), "°C")
        min_t = _v(d.get("temp_min"), "°C")
        rain_pct = d.get("rain_chance_pct", 0)
        rain_mm = d.get("rain_expected_mm", 0)

        if lang == "hi":
            lines.append(f"📅 *{day_label}*: {condition}")
            lines.append(f"   तापमान: {min_t} से {max_t} | बारिश की संभावना: {rain_pct}% ({rain_mm} मिमी)")
        else:
            lines.append(f"📅 *{day_label}*: {condition}")
            lines.append(f"   Temp: {min_t} to {max_t} | Rain Chance: {rain_pct}% ({rain_mm} mm)")
        lines.append("")

    lines.append(t(lang, "disclaimer"))
    return "\n".join(lines).strip()


def format_risk(lang: str, risk: dict, node_name: str, distance_km: float) -> str:
    """Format comprehensive flood and heat risk analysis (Parul's logic)."""
    lang = i18n.norm_lang(lang)
    out = [t(lang, "current_title", name=node_name, km=distance_km), ""]

    for kind, advice in (("flood", FLOOD_ADVICE), ("heat", HEAT_ADVICE)):
        res = risk.get(kind) or {"level_name": "UNKNOWN", "stale": True, "reasons": []}
        if kind == "heat" and res.get("stale"):
            continue

        label = t(lang, f"{kind}_word")
        level_name = res.get("level_name", "UNKNOWN")
        out.append(f"{label}: {level_label(lang, level_name)}")

        advice_text = advice.get(lang, {}).get(level_name) or advice["en"].get(level_name, "")
        out.append(advice_text)

        reasons = res.get("reasons") or []
        if reasons and level_name != "GREEN":
            out.append(t(lang, "why"))
            out += [f"• {reason_text(lang, r)}" for r in reasons]

        out.append("")

    out.append(t(lang, "disclaimer"))
    return "\n".join(out).strip()


def format_crop(lang: str, advice: dict) -> str:
    """Format crop recommendations with irrigation context and agricultural disclaimer."""
    lang = i18n.norm_lang(lang)
    mode = t(lang, "mode_irrigated" if advice.get("irrigated") else "mode_rainfed")
    season_key = advice.get("season", "rabi")
    season_name = SEASON.get(lang, {}).get(season_key, season_key.capitalize())

    out = [t(lang, "crop_title", season=season_name, mode=mode), ""]
    recs = advice.get("recommendations") or []

    if not recs:
        out.append(t(lang, "crop_none"))
    else:
        for i, r in enumerate(recs, 1):
            name = r.get("name_hi") if lang == "hi" else r.get("name_en", "Crop")
            score_pct = round(r.get("score", 0) * 100)
            out.append(f"{i}. *{name}* ({score_pct}%)")

            for reason in r.get("reasons", []):
                tpl = CROP_REASONS.get(lang, {}).get(reason.get("code")) or CROP_REASONS["en"].get(reason.get("code"))
                if tpl:
                    try:
                        out.append("   - " + tpl.format(**reason.get("params", {})))
                    except Exception:
                        pass

    out += ["", t(lang, "crop_footer")]
    return "\n".join(out)


def format_alert(lang: str, alert: dict, node_name: str) -> str:
    """Format high-priority automated push notification alert."""
    lang = i18n.norm_lang(lang)
    kind = alert.get("kind", "flood")
    advice = FLOOD_ADVICE if kind == "flood" else HEAT_ADVICE

    lvl = alert.get("level", 0)
    prev = alert.get("previous_level", 0)
    up = lvl > prev
    head = t(lang, "alert_up" if up else "alert_down", name=node_name)

    level_name = alert.get("level_name", "UNKNOWN")
    out = [
        f"{LEVEL_EMOJI.get(level_name, '⚪')} *{head}*",
        f"{t(lang, kind + '_word')}: {level_label(lang, level_name)}",
        advice.get(lang, {}).get(level_name, "")
    ]

    reasons = alert.get("reasons") or []
    if reasons and level_name != "GREEN":
        out.append(t(lang, "why"))
        out += [f"• {reason_text(lang, r)}" for r in reasons[:4]]

    out += ["", t(lang, "disclaimer")]
    return "\n".join(out)


def format_sms(lang: str, alert: dict, node_name: str) -> str:
    """Format short SMS message for critical RED alerts only."""
    kind = alert.get("kind", "flood")
    return t(lang, "sms_flood" if kind == "flood" else "sms_heat", name=node_name)
