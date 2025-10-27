import logging
from typing import Any, Optional


class WhatsAppClient:
    """
    Stub WhatsApp sender client.

    This implementation logs outbound messages for local testing. When you obtain
    WhatsApp Cloud API credentials (WABA), you can extend this class to perform
    real HTTP requests to the Graph API.

    Planned real send (for future):
    - Text:
      POST https://graph.facebook.com/v20.0/{phone_number_id}/messages
      Headers: Authorization: Bearer {token}
      Body:
        {
          "messaging_product": "whatsapp",
          "to": "+40700000000",
          "type": "text",
          "text": { "body": "Hello world" }
        }

    - Image:
      POST https://graph.facebook.com/v20.0/{phone_number_id}/messages
      {
        "messaging_product": "whatsapp",
        "to": "+40700000000",
        "type": "image",
        "image": {
          "link": "https://example.com/image.jpg",
          "caption": "optional"
        }
      }
    """

    def __init__(
        self,
        token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        base_url: str = "https://graph.facebook.com/v20.0",
    ) -> None:
        self.logger = logging.getLogger("WhatsAppClient")
        self.token = token
        self.phone_number_id = phone_number_id
        self.base_url = base_url

        if not self.token or not self.phone_number_id:
            self.logger.info(
                "WhatsAppClient initialized in stub mode (no token/phone_number_id). "
                "Outbound messages will be logged only."
            )

    def send_text(self, phone: str, text: str) -> None:
        """
        Stub: log outbound text message.
        """
        self.logger.info("[WHA OUT] to %s: %s", phone, text)

    def send_image(self, phone: str, image_bytes_or_path: Any, caption: Optional[str] = None) -> None:
        """
        Stub: log outbound image message intent.

        image_bytes_or_path may be:
        - bytes / bytearray (in-memory image)
        - str path to a local file
        - file-like object with .name attribute
        """
        try:
            kind = type(image_bytes_or_path).__name__
        except Exception:
            kind = "unknown"
        self.logger.info("[WHA OUT IMAGE] to %s: caption=%s image_kind=%s", phone, caption, kind)

    # Future real send methods (commented placeholders):
    # def _post(self, endpoint: str, payload: dict) -> dict:
    #     if not self.token or not self.phone_number_id:
    #         raise RuntimeError("WhatsAppClient missing token/phone_number_id for real sends")
    #     url = f"{self.base_url}/{self.phone_number_id}/{endpoint}"
    #     headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    #     resp = requests.post(url, headers=headers, json=payload, timeout=15)
    #     resp.raise_for_status()
    #     return resp.json()