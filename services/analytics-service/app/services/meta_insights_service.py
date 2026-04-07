import time

import structlog
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.exceptions import FacebookRequestError
from facebook_business.session import FacebookSession

from app.config import settings
from shared.utils.meta_credentials import get_meta_credentials

logger = structlog.get_logger()

INSIGHTS_FIELDS = [
    "impressions",
    "clicks",
    "spend",
    "actions",
    "ctr",
    "cpc",
    "cost_per_action_type",
]


class MetaInsightsService:
    """
    Fetches performance metrics from Meta Insights API using facebook-business SDK.
    MVP: Uses single token from env vars via get_meta_credentials().
    """

    def __init__(self, user_id: str | None = None):
        creds = get_meta_credentials(user_id)
        session = FacebookSession(
            app_id=settings.META_APP_ID,
            app_secret=settings.META_APP_SECRET,
            access_token=creds.access_token,
        )
        self.api = FacebookAdsApi(session)
        self.ad_account_id = creds.ad_account_id

    def fetch_ad_insights(
        self, meta_ad_id: str, date_from: str, date_to: str
    ) -> list[dict]:
        """
        Fetch insights for a specific ad within a date range.
        Returns list of daily metric dicts.
        """
        params = {
            "time_range": {"since": date_from, "until": date_to},
            "time_increment": 1,
            "level": "ad",
        }

        for attempt in range(3):
            try:
                ad = Ad(meta_ad_id, api=self.api)
                insights = ad.get_insights(fields=INSIGHTS_FIELDS, params=params)
                return [self._parse_insight(row, meta_ad_id) for row in insights]

            except FacebookRequestError as e:
                error_code = e.api_error_code()

                if error_code == 190:
                    logger.critical(
                        "meta_token_expired",
                        meta_ad_id=meta_ad_id,
                        error=str(e),
                    )
                    raise

                if error_code in (17, 613):
                    if attempt < 2:
                        wait = 2 ** attempt * 30
                        logger.warning(
                            "meta_rate_limit",
                            meta_ad_id=meta_ad_id,
                            attempt=attempt + 1,
                            wait_seconds=wait,
                        )
                        time.sleep(wait)
                        continue
                    logger.error(
                        "meta_rate_limit_exhausted",
                        meta_ad_id=meta_ad_id,
                    )
                    raise

                if error_code == 100:
                    logger.error(
                        "meta_invalid_parameter",
                        meta_ad_id=meta_ad_id,
                        error=str(e),
                    )
                    return []

                logger.error(
                    "meta_insights_error",
                    meta_ad_id=meta_ad_id,
                    error_code=error_code,
                    error=str(e),
                )
                raise

        return []

    def fetch_all_active_ads_insights(
        self, date_from: str, date_to: str
    ) -> list[dict]:
        """
        Fetch insights for ALL active ads in the ad account.
        Uses AdAccount.get_insights() with level='ad' for efficiency.
        """
        params = {
            "time_range": {"since": date_from, "until": date_to},
            "time_increment": 1,
            "level": "ad",
            "filtering": [
                {"field": "ad.effective_status", "operator": "IN", "value": ["ACTIVE"]}
            ],
        }

        for attempt in range(3):
            try:
                account = AdAccount(self.ad_account_id, api=self.api)
                insights = account.get_insights(
                    fields=INSIGHTS_FIELDS + ["ad_id"], params=params
                )
                return [self._parse_insight(row) for row in insights]

            except FacebookRequestError as e:
                error_code = e.api_error_code()

                if error_code == 190:
                    logger.critical("meta_token_expired", error=str(e))
                    raise

                if error_code in (17, 613):
                    if attempt < 2:
                        wait = 2 ** attempt * 30
                        logger.warning(
                            "meta_rate_limit",
                            attempt=attempt + 1,
                            wait_seconds=wait,
                        )
                        time.sleep(wait)
                        continue
                    raise

                logger.error(
                    "meta_account_insights_error",
                    error_code=error_code,
                    error=str(e),
                )
                raise

        return []

    @staticmethod
    def _parse_insight(row: dict, meta_ad_id: str | None = None) -> dict:
        """Parse a single insight row into our metric format."""
        ad_id = meta_ad_id or row.get("ad_id", "")

        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))

        # Meta returns spend as string in account currency (e.g. "23.50")
        spend_str = row.get("spend", "0")
        spend_cents = int(round(float(spend_str) * 100))

        ctr = float(row.get("ctr", 0))
        cpc_str = row.get("cpc", "0")
        cpc_cents = int(round(float(cpc_str) * 100)) if cpc_str else 0

        # Extract conversions from actions array
        conversions = 0
        actions = row.get("actions", [])
        if actions:
            for action in actions:
                action_type = action.get("action_type", "")
                if action_type in (
                    "onsite_conversion.messaging_conversation_started_7d",
                    "onsite_conversion.messaging_conversation_started",
                    "messages",
                ):
                    conversions += int(action.get("value", 0))

        # ROAS: default 0.0 since WhatsApp conversions don't have direct revenue
        roas = 0.0

        return {
            "meta_ad_id": ad_id,
            "date": row.get("date_start", ""),
            "impressions": impressions,
            "clicks": clicks,
            "spend_cents": spend_cents,
            "conversions": conversions,
            "ctr": round(ctr, 4),
            "cpc_cents": cpc_cents,
            "roas": roas,
        }
