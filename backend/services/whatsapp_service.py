
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def send_daily_summary_template(
    recipient: str,
    appointment_date: str,
    summary: str,
) -> dict:
    """
    Send an approved WhatsApp template containing
    the next day's appointment summary.
    """

    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    api_version = os.getenv("WHATSAPP_API_VERSION")
    template_name = os.getenv(
        "WHATSAPP_TEMPLATE_NAME",
        "daily_appointment_summary",
    )
    template_language = os.getenv(
        "WHATSAPP_TEMPLATE_LANGUAGE",
        "en_US",
    )

    missing = [
        name
        for name, value in {
            "WHATSAPP_ACCESS_TOKEN": access_token,
            "WHATSAPP_PHONE_NUMBER_ID": phone_number_id,
            "WHATSAPP_API_VERSION": api_version,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing WhatsApp configuration: "
            + ", ".join(missing)
        )

    url = (
        f"https://graph.facebook.com/"
        f"{api_version}/{phone_number_id}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": template_language,
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": appointment_date,
                        },
                        {
                            "type": "text",
                            "text": summary,
                        },
                    ],
                }
            ],
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        # Avoid logging credentials or exposing tokens.
        raise RuntimeError(
            "WhatsApp rejected the message: "
            f"HTTP {exc.response.status_code}; "
            f"{exc.response.text[:1000]}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not connect to WhatsApp: {exc}"
        ) from exc



def send_whatsapp_text_message(recipient: str, text: str) -> dict:
    """
    Send a free-form text message to a WhatsApp user
    via the WhatsApp Cloud API.
    """

    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    api_version = os.getenv("WHATSAPP_API_VERSION")

    missing = [
        name
        for name, value in {
            "WHATSAPP_ACCESS_TOKEN": access_token,
            "WHATSAPP_PHONE_NUMBER_ID": phone_number_id,
            "WHATSAPP_API_VERSION": api_version,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing WhatsApp configuration: "
            + ", ".join(missing)
        )

    url = (
        f"https://graph.facebook.com/"
        f"{api_version}/{phone_number_id}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"body": text},
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            "WhatsApp rejected the message: "
            f"HTTP {exc.response.status_code}; "
            f"{exc.response.text[:1000]}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not connect to WhatsApp: {exc}"
        ) from exc



def get_whatsapp_session_id(phone: str) -> str:
    """
    Create a stable session ID for a WhatsApp user.

    The same phone number always produces
    the same session ID.
    """

    clean_phone = phone.strip().replace("+", "")

    return f"whatsapp_{clean_phone}"