from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import os

from services.whatsapp_service import (
    get_whatsapp_session_id,
    send_whatsapp_text_message,
)
from ai_agent import run_agent

router = APIRouter(
    prefix="/whatsapp",
    tags=["WhatsApp"]
)
class WhatsAppWebhookRequest(BaseModel):
    entry: list

@router.get("/webhook")
async def verify_whatsapp_webhook(request: Request):
    """
    WhatsApp webhook verification endpoint.

    Meta will use this endpoint when configuring
    the WhatsApp webhook.
    """

    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    print("WhatsApp webhook verification received")
    print("Mode:", mode)
    print("Token:", token)
    print("Challenge:", challenge)

    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    if mode == "subscribe" and token == verify_token:
        return PlainTextResponse(str(challenge))

    return {
        "success": False,
        "message": "Webhook verification failed."
    }


@router.post("/webhook")
async def receive_whatsapp_message(
    request: WhatsAppWebhookRequest
):
    data = request.model_dump()

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        messages = value.get("messages", [])

        if not messages:
            return {
                "success": True,
                "message": "No message received."
            }

        message = messages[0]

        sender_phone = message["from"]
        message_id = message["id"]
        message_type = message["type"]

        if message_type != "text":
            return {
                "success": True,
                "message": "Unsupported message type."
            }

        text = message["text"]["body"]

        session_id = get_whatsapp_session_id(sender_phone)

        response = run_agent(
            session_id,
            text,
            sender_phone
        )

        # Send the AI reply back to the patient on WhatsApp.
        try:
            send_whatsapp_text_message(sender_phone, response)
        except Exception as e:
            print("Failed to send WhatsApp reply:", e)

        return {
            "success": True,
            "phone": sender_phone,
            "session_id": session_id,
            "message_id": message_id,
            "message": text,
            "response": response
        }

    except (KeyError, IndexError, TypeError) as e:
        print("Invalid WhatsApp webhook payload:", e)

        return {
            "success": False,
            "message": "Invalid WhatsApp webhook payload."
        }