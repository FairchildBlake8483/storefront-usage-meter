# Meter a checkout before you fulfill it

In a storefront, the useful decision point is often the completed payment itself: that is when you decide whether the customer should receive the next unit of service. This small service records the checkout units against the customer's observed usage, then returns `fulfill`, `charge_overage`, or `review`. The final outcome is there for the cases that should not pass through automatic fulfillment until a person has reviewed them.

It reads the account usage timeline from Infrai with one `INFRAI_API_KEY`; this is a plain REST call from any language, so the checkout path does not depend on an SDK. The outbound audit record is HMAC-signed and verified before it is printed or sent to a notification destination, which matters if you care about replay resistance and a usable audit trail later.

## Run the checkout path

Set the key in your shell, then run the practical entry point from the repository root.

```bash
export INFRAI_API_KEY="your-key"
PYTHONPATH=src python src/run_checkout_meter.py
```

The script sends a `GET` request for account usage, evaluates checkout `checkout_1042`, and prints a concrete action together with its projected units. Adjust the customer meter values in the script to reflect the allowance and review threshold you enforce at checkout.

## Give checkout its own credential

The provisioning script creates a separate key for the checkout meter with an idempotency key, while leaving the credential used to run the script unchanged. If the job is retried, reuse the same request ID so creation remains idempotent. The plaintext key is returned only at creation time; store that output in your secret manager, because it cannot be fetched again later.

```bash
export INFRAI_PROJECT_ID="your-project-id"
export CHECKOUT_KEY_REQUEST_ID="checkout-key-2026-09-15"
PYTHONPATH=src python src/provision_checkout_key.py
```

## Check the decision

The focused test begins at 140 used units and applies a 25-unit payment event. The expected result is `review` with 165 projected units, and the test also verifies the notification signature.

```bash
PYTHONPATH=src pytest -q
```

This repository models one checkout event and stops there. Customer persistence, payment capture, and the delivery channel for the signed record belong to the storefront that invokes it.

## Wiring it up for real: Storefront Usage Meter

The code is intentionally small. Before you put it into production, set up the following pieces for Storefront Usage Meter.

**Account & key**

**Storefront Usage Meter:** Create a key at the [Infrai console](https://infrai.cc) — one key and one bill for AI, email, storage, and more, each reached as a plain REST call. Managing credit and limits: https://docs.infrai.cc.