from dataclasses import dataclass
import os


@dataclass
class MetaCredentials:
    access_token: str
    ad_account_id: str
    page_id: str
    whatsapp_number: str


def get_meta_credentials(user_id: str | None = None) -> MetaCredentials:
    """
    MVP: Returns owner's Meta credentials from environment variables.
    Future multi-user: Will query ad_accounts table by user_id and decrypt token.

    The user_id parameter is accepted but ignored in MVP mode,
    ensuring all call sites are already multi-user-ready.
    """
    return MetaCredentials(
        access_token=os.environ.get("META_ACCESS_TOKEN", ""),
        ad_account_id=os.environ.get("META_AD_ACCOUNT_ID", ""),
        page_id=os.environ.get("META_PAGE_ID", ""),
        whatsapp_number=os.environ.get("META_WHATSAPP_NUMBER", ""),
    )
