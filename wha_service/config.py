import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """
    WhatsApp service configuration (stub-friendly).
    If WABA_TOKEN and WABA_PHONE_NUMBER_ID are provided, the WhatsAppClient can be initialized
    for real sends; otherwise the service will operate in stub mode and log outbound messages.
    """
    WABA_TOKEN: Optional[str]
    WABA_PHONE_NUMBER_ID: Optional[str]
    WHA_VERIFY_TOKEN: Optional[str]
    NO_POSTER_PATH: Optional[str]


def load_settings() -> Settings:
    """
    Load environment variables into a Settings object.
    """
    return Settings(
        WABA_TOKEN=os.getenv("WABA_TOKEN"),
        WABA_PHONE_NUMBER_ID=os.getenv("WABA_PHONE_NUMBER_ID"),
        WHA_VERIFY_TOKEN=os.getenv("WHA_VERIFY_TOKEN"),
        NO_POSTER_PATH=os.getenv("NO_POSTER_PATH"),
    )