"""Run one storefront checkout decision against the account usage timeline."""

from checkout_meter import (
    CustomerMeter,
    PaymentEvent,
    client_from_environment,
    decide_checkout,
    signed_audit_notification,
    verify_audit_notification,
)


def units_from_timeseries(data: dict) -> int:
    points = data.get("data", data.get("items", []))
    return sum(int(point.get("usage", 0)) for point in points if isinstance(point, dict))


def main() -> None:
    client = client_from_environment()
    timeline = client.account_usage_timeseries()
    event = PaymentEvent("cus_amber", "checkout_1042", units=18, amount_usd=42)
    meter = CustomerMeter("cus_amber", included_units=120, review_threshold_units=160)
    decision = decide_checkout(meter, event, units_from_timeseries(timeline))
    audit = signed_audit_notification(event, decision, "local-audit-secret")
    assert verify_audit_notification(audit, "local-audit-secret")
    print({"checkout_id": event.checkout_id, "action": decision.action, "projected_units": decision.projected_units})


if __name__ == "__main__":
    main()
