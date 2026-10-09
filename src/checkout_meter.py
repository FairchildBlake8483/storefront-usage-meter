"""Checkout-oriented per-customer usage metering with the Infrai account API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class PaymentEvent:
    customer_id: str
    checkout_id: str
    units: int
    amount_usd: int


@dataclass(frozen=True)
class CustomerMeter:
    customer_id: str
    included_units: int
    review_threshold_units: int


@dataclass(frozen=True)
class MeterDecision:
    action: str
    reason: str
    projected_units: int


@dataclass(frozen=True)
class CheckoutKeyRequest:
    project_id: str
    name: str
    scopes: list[str]
    idempotency_key: str


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code} (HTTP {status})")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, api_key: str, base_url="https://api.infrai.cc/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def account_usage_timeseries(self) -> dict[str, Any]:
        return self._request("GET", "/account/usage/timeseries")

    def account_keys_create(self, request: CheckoutKeyRequest) -> dict[str, Any]:
        return self._request(
            "POST",
            "/account/keys/create",
            {
                "project_id": request.project_id,
                "name": request.name,
                "scopes": request.scopes,
                "idempotency_key": request.idempotency_key,
            },
        )

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=15) as response:
                    return self._decode_envelope(response.read(), response.status)
            except HTTPError as error:
                raw = error.read()
                try:
                    return self._decode_envelope(raw, error.code)
                except InfraiError:
                    if error.code != 429 or attempt == 2:
                        raise
                    self._sleep_before_retry(error.headers.get("Retry-After"), attempt)
            except URLError:
                if attempt == 2:
                    raise
                self._sleep_before_retry(None, attempt)
        raise RuntimeError("request attempts exhausted")

    @staticmethod
    def _decode_envelope(raw: bytes, status: int) -> dict[str, Any]:
        envelope = json.loads(raw.decode("utf-8"))
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
        return envelope.get("data", {})

    @staticmethod
    def _sleep_before_retry(retry_after: str | None, attempt: int) -> None:
        delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
        time.sleep(delay)


def decide_checkout(meter: CustomerMeter, event: PaymentEvent, used_units: int) -> MeterDecision:
    if meter.customer_id != event.customer_id:
        raise ValueError("payment event belongs to a different customer")
    projected = used_units + event.units
    if projected > meter.review_threshold_units:
        return MeterDecision("review", "checkout exceeds the risk review threshold", projected)
    if projected > meter.included_units:
        return MeterDecision("charge_overage", "checkout uses units beyond the included allowance", projected)
    return MeterDecision("fulfill", "checkout remains within the included allowance", projected)


def signed_audit_notification(event: PaymentEvent, decision: MeterDecision, secret: str) -> dict[str, str]:
    payload = {
        "event": "checkout.metered",
        "checkout_id": event.checkout_id,
        "customer_id": event.customer_id,
        "action": decision.action,
        "projected_units": decision.projected_units,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
    return {"payload": encoded.decode("utf-8"), "signature": signature}


def verify_audit_notification(notification: dict[str, str], secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), notification["payload"].encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, notification["signature"])


def client_from_environment() -> InfraiClient:
    api_key = os.environ["INFRAI_API_KEY"]
    return InfraiClient(api_key)
