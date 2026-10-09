"""Create a separate checkout credential without touching the key running this script."""

import os

from checkout_meter import CheckoutKeyRequest, client_from_environment


def main() -> None:
    project_id = os.environ.get("INFRAI_PROJECT_ID", "")
    idempotency_key = os.environ.get("CHECKOUT_KEY_REQUEST_ID", "")
    if not project_id or not idempotency_key:
        raise SystemExit("Set INFRAI_PROJECT_ID and CHECKOUT_KEY_REQUEST_ID before creating the checkout credential.")
    client = client_from_environment()
    created = client.account_keys_create(
        CheckoutKeyRequest(
            project_id=project_id,
            name="storefront-checkout-meter",
            scopes=["account.usage.timeseries"],
            idempotency_key=idempotency_key,
        )
    )
    print(created)


if __name__ == "__main__":
    main()
