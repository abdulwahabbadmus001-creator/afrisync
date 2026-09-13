import argparse
import sys

from server import email_delivery_status_payload, send_email_message


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a test AfriSync email using the configured SMTP sender.")
    parser.add_argument("recipient", help="Recipient email address to test, e.g. user@gmail.com")
    args = parser.parse_args()

    status = email_delivery_status_payload()
    print("Email delivery status:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    if not status.get("smtp_configured"):
        print("\nSMTP is not configured. Create afrisync_email_config.ps1 and restart the server.")
        return 1

    result = send_email_message(
        args.recipient,
        "AfriSync test email",
        "This is a test email from AfriSync. If you received this, real email delivery is working.",
    )
    print("\nSend result:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    return 0 if result.get("sent") else 1


if __name__ == "__main__":
    raise SystemExit(main())
