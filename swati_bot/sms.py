"""SMS fallback dispatch for critical RED alerts (Swati's Bot).

Default mode is DryRunSender so that no SMS charges or unintended messages occur during
development or viva demos.
"""
import logging
import os
import re
import requests

log = logging.getLogger("sms")

# Strict regex matching valid Indian 10-digit mobile numbers with +91 country prefix
INDIAN_MOBILE = re.compile(r"^\+91[6-9]\d{9}$")


def valid_phone(p: str | None) -> bool:
    """Validate Indian mobile numbers in format +919876543210."""
    return bool(p and INDIAN_MOBILE.match(p))


class DryRunSender:
    """Safe sender for testing and evaluation; prints SMS to log without sending real SMS."""
    def __init__(self):
        self.sent = []

    def send(self, to: str, body: str) -> bool:
        log.warning("[SMS DRY-RUN] TO: %s | BODY: %s", to, body)
        self.sent.append((to, body))
        return True


class TwilioSender:
    """Optional Twilio REST API integration for real SMS dispatch."""
    def __init__(self, sid: str, token: str, from_number: str, session=requests):
        self.sid = sid
        self.token = token
        self.from_ = from_number
        self.s = session

    def send(self, to: str, body: str) -> bool:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json"
            r = self.s.post(
                url,
                data={"To": to, "From": self.from_, "Body": body},
                auth=(self.sid, self.token),
                timeout=15,
            )
            ok = r.status_code in (200, 201)
            if not ok:
                log.error("Twilio SMS send error: status %s, response %s", r.status_code, r.text)
            return ok
        except Exception:
            log.exception("Twilio SMS exception")
            return False


def make_sender_from_env():
    """Factory creating appropriate SMS sender from environment or configuration."""
    provider = os.environ.get("SMS_PROVIDER", "dryrun").lower()
    if provider == "twilio":
        sid = os.environ.get("TWILIO_SID", "")
        token = os.environ.get("TWILIO_TOKEN", "")
        from_num = os.environ.get("TWILIO_FROM", "")
        if sid and token and from_num:
            return TwilioSender(sid, token, from_num)
        log.warning("Twilio credentials missing; falling back to DryRunSender")
    return DryRunSender()
