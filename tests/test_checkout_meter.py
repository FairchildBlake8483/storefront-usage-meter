from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from checkout_meter import CustomerMeter, PaymentEvent, decide_checkout, signed_audit_notification, verify_audit_notification


def test_large_checkout_is_held_for_review_and_audit_signature_verifies() -> None:
    meter = CustomerMeter("cus_amber", included_units=120, review_threshold_units=150)
    event = PaymentEvent("cus_amber", "checkout_1042", units=25, amount_usd=42)

    decision = decide_checkout(meter, event, used_units=140)
    audit = signed_audit_notification(event, decision, "test-secret")

    assert decision.action == "review"
    assert decision.projected_units == 165
    assert verify_audit_notification(audit, "test-secret")
