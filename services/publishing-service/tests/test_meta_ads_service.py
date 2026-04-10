import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

from facebook_business.exceptions import FacebookRequestError

from app.services.meta_ads_service import MetaAdsService
from app.services.meta_exceptions import (
    MetaTokenInvalidError,
    MetaRateLimitError,
    MetaInvalidParameterError,
    MetaMissingPermissionError,
    MetaValidationError,
)


def _make_fb_error(error_code: int, message: str = "test error"):
    """Create a mock FacebookRequestError."""
    exc = MagicMock()
    exc.api_error_code.return_value = error_code
    exc.api_error_message.return_value = message
    exc.api_error_subcode.return_value = None
    exc.body.return_value = {"error": {"message": message, "code": error_code}}
    return exc


@patch("app.services.meta_ads_service.FacebookSession")
@patch("app.services.meta_ads_service.FacebookAdsApi")
class TestMetaAdsService:

    def test_constructor_creates_per_user_api(self, mock_api_cls, mock_session_cls):
        service = MetaAdsService("test_token")
        mock_session_cls.assert_called_once()
        mock_api_cls.assert_called_once_with(mock_session_cls.return_value)
        assert service.api == mock_api_cls.return_value

    @patch("app.services.meta_ads_service.AdAccount")
    def test_create_campaign_success(self, mock_account_cls, mock_api_cls, mock_session_cls):
        mock_account = MagicMock()
        mock_account.create_campaign.return_value = {"id": "camp_123"}
        mock_account_cls.return_value = mock_account

        service = MetaAdsService("test_token")
        result = service.create_campaign(
            ad_account_id="act_123",
            name="Test Campaign",
            objective="OUTCOME_ENGAGEMENT",
            special_ad_categories=[],
        )
        assert result == "camp_123"
        mock_account.create_campaign.assert_called_once()

    @patch("app.services.meta_ads_service.MetaLocationResolver")
    @patch("app.services.meta_ads_service.AdAccount")
    def test_create_adset_with_whatsapp_targeting(self, mock_account_cls, mock_resolver_cls, mock_api_cls, mock_session_cls):
        mock_account = MagicMock()
        mock_account.create_ad_set.return_value = {"id": "adset_123"}
        mock_account_cls.return_value = mock_account

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = ({"countries": ["CO"]}, {"countries": ["CO"]})
        mock_resolver_cls.return_value = mock_resolver

        service = MetaAdsService("test_token")
        # Mock resolve_interest_ids to avoid SDK calls
        service.resolve_interest_ids = MagicMock(return_value=[{"id": "6003", "name": "fashion"}])

        adset_id, resolved_geo = service.create_adset(
            ad_account_id="act_123",
            campaign_id="camp_123",
            name="Test AdSet",
            daily_budget_cents=5000,
            target_audience={
                "age_min": 25,
                "age_max": 35,
                "genders": ["female"],
                "interests": ["fashion"],
                "locations": ["CO"],
            },
            page_id="page_123",
            whatsapp_phone_number="+573001234567",
        )
        assert adset_id == "adset_123"
        assert resolved_geo == {"countries": ["CO"]}

        # Verify WhatsApp-specific params
        call_params = mock_account.create_ad_set.call_args[1]["params"]
        assert call_params["destination_type"] == "WHATSAPP"
        assert call_params["promoted_object"]["page_id"] == "page_123"
        assert call_params["promoted_object"]["whatsapp_phone_number"] == "+573001234567"

    @patch("app.services.meta_ads_service.AdAccount")
    def test_create_adcreative_whatsapp_cta(self, mock_account_cls, mock_api_cls, mock_session_cls):
        mock_account = MagicMock()
        mock_account.create_ad_creative.return_value = {"id": "creative_123"}
        mock_account_cls.return_value = mock_account

        service = MetaAdsService("test_token")
        result = service.create_adcreative(
            ad_account_id="act_123",
            name="Test Creative",
            page_id="page_123",
            image_hash="abc123hash",
            copy_text="Buy now!",
            whatsapp_phone_number="+573001234567",
        )
        assert result == "creative_123"

        call_params = mock_account.create_ad_creative.call_args[1]["params"]
        link_data = call_params["object_story_spec"]["link_data"]
        assert link_data["link"] == "https://api.whatsapp.com/send"
        assert link_data["call_to_action"]["type"] == "WHATSAPP_MESSAGE"
        assert "page_welcome_message" not in link_data

    @patch("app.services.meta_ads_service.AdAccount")
    def test_create_campaign_sets_special_ad_categories(self, mock_account_cls, mock_api_cls, mock_session_cls):
        mock_account = MagicMock()
        mock_account.create_campaign.return_value = {"id": "camp_456"}
        mock_account_cls.return_value = mock_account

        service = MetaAdsService("test_token")
        service.create_campaign(
            ad_account_id="act_123",
            name="Test",
            objective="OUTCOME_ENGAGEMENT",
            special_ad_categories=[],
        )

        call_params = mock_account.create_campaign.call_args[1]["params"]
        assert "special_ad_categories" in call_params
        assert call_params["special_ad_categories"] == []

    @patch("app.services.meta_ads_service.MetaLocationResolver")
    @patch("app.services.meta_ads_service.AdAccount")
    def test_budget_passed_in_cents(self, mock_account_cls, mock_resolver_cls, mock_api_cls, mock_session_cls):
        mock_account = MagicMock()
        mock_account.create_ad_set.return_value = {"id": "adset_789"}
        mock_account_cls.return_value = mock_account

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = ({"countries": ["CO"]}, {"countries": ["CO"]})
        mock_resolver_cls.return_value = mock_resolver

        service = MetaAdsService("test_token")
        service.resolve_interest_ids = MagicMock(return_value=[])

        service.create_adset(
            ad_account_id="act_123",
            campaign_id="camp_123",
            name="Budget Test",
            daily_budget_cents=10000,
            target_audience={"age_min": 18, "age_max": 65, "locations": ["CO"]},
            page_id="page_123",
            whatsapp_phone_number="+573001234567",
        )

        call_params = mock_account.create_ad_set.call_args[1]["params"]
        assert call_params["daily_budget"] == "10000"


@patch("app.services.meta_ads_service.FacebookSession")
@patch("app.services.meta_ads_service.FacebookAdsApi")
class TestMetaAdsServiceErrorHandling:

    def test_error_190_raises_token_invalid(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_exc = MagicMock(spec=FacebookRequestError)
        mock_exc.api_error_code.return_value = 190
        mock_exc.api_error_message.return_value = "Token expired"
        mock_exc.api_error_subcode.return_value = None

        from app.services.meta_ads_service import _handle_meta_error
        with pytest.raises(MetaTokenInvalidError):
            _handle_meta_error(mock_exc)

    def test_error_17_raises_rate_limit(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_exc = MagicMock(spec=FacebookRequestError)
        mock_exc.api_error_code.return_value = 17
        mock_exc.api_error_message.return_value = "Rate limit"
        mock_exc.api_error_subcode.return_value = None

        from app.services.meta_ads_service import _handle_meta_error
        with pytest.raises(MetaRateLimitError):
            _handle_meta_error(mock_exc)

    def test_error_613_raises_rate_limit(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_exc = MagicMock(spec=FacebookRequestError)
        mock_exc.api_error_code.return_value = 613
        mock_exc.api_error_message.return_value = "Rate limit"
        mock_exc.api_error_subcode.return_value = None

        from app.services.meta_ads_service import _handle_meta_error
        with pytest.raises(MetaRateLimitError):
            _handle_meta_error(mock_exc)

    def test_error_100_raises_invalid_parameter(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_exc = MagicMock(spec=FacebookRequestError)
        mock_exc.api_error_code.return_value = 100
        mock_exc.api_error_message.return_value = "Invalid param"
        mock_exc.api_error_subcode.return_value = None

        from app.services.meta_ads_service import _handle_meta_error
        with pytest.raises(MetaInvalidParameterError):
            _handle_meta_error(mock_exc)

    def test_error_275_raises_missing_permission(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_exc = MagicMock(spec=FacebookRequestError)
        mock_exc.api_error_code.return_value = 275
        mock_exc.api_error_message.return_value = "Missing permission"
        mock_exc.api_error_subcode.return_value = None

        from app.services.meta_ads_service import _handle_meta_error
        with pytest.raises(MetaMissingPermissionError):
            _handle_meta_error(mock_exc)

    def test_error_1487901_raises_validation(self, mock_api_cls, mock_session_cls):
        from facebook_business.exceptions import FacebookRequestError

        mock_exc = MagicMock(spec=FacebookRequestError)
        mock_exc.api_error_code.return_value = 1487901
        mock_exc.api_error_message.return_value = "Validation error"
        mock_exc.api_error_subcode.return_value = None
        mock_exc.body.return_value = {
            "error": {"error_data": {"blame_field_specs": [["targeting"]]}}
        }

        from app.services.meta_ads_service import _handle_meta_error
        with pytest.raises(MetaValidationError) as exc_info:
            _handle_meta_error(mock_exc)
        assert exc_info.value.blame_field_specs == [["targeting"]]


class TestUploadImage:
    """Test that AdImage is instantiated with parent_id in constructor (Bug #1)."""

    @patch("app.services.meta_ads_service.FacebookSession")
    @patch("app.services.meta_ads_service.FacebookAdsApi")
    @patch("app.services.meta_ads_service.AdImage")
    @patch("app.services.meta_ads_service.httpx.Client")
    def test_upload_image_passes_parent_id_in_constructor(
        self, MockHttpClient, MockAdImage, mock_api_cls, mock_session_cls
    ):
        """Bug #1: parent_id MUST be passed to AdImage() constructor, not to remote_create(params)."""
        mock_image_instance = MagicMock()
        mock_image_instance.__getitem__ = MagicMock(return_value="abc123")
        MockAdImage.return_value = mock_image_instance
        MockAdImage.Field = MagicMock()
        MockAdImage.Field.filename = "filename"
        MockAdImage.Field.hash = "hash"

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.content = b"fake_image_bytes"
        mock_response.raise_for_status = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_instance.get.return_value = mock_response
        MockHttpClient.return_value = mock_client_instance

        service = MetaAdsService.__new__(MetaAdsService)
        service.api = MagicMock()

        try:
            service.upload_image("act_123456789", "https://example.com/image.png")
        except Exception:
            pass  # We only care about how AdImage was instantiated

        # CRITICAL: parent_id must be in the constructor call
        MockAdImage.assert_called_once()
        call_kwargs = MockAdImage.call_args
        assert call_kwargs.kwargs.get("parent_id") == "act_123456789", \
            "AdImage MUST receive parent_id as constructor argument"

        # CRITICAL: remote_create must be called WITHOUT parent_id in params
        mock_image_instance.remote_create.assert_called_once()
        if mock_image_instance.remote_create.call_args:
            create_kwargs = mock_image_instance.remote_create.call_args.kwargs
            create_params = create_kwargs.get("params", {})
            assert "parent_id" not in create_params, \
                "parent_id must NOT be in remote_create(params={})"


class TestAllSdkObjectsUseConstructorParentId:
    """Comprehensive check: no SDK call passes parent_id via params (Bug #1 extended)."""

    def test_no_parent_id_in_params(self):
        """Grep the source to verify no SDK call passes parent_id via params."""
        source = Path("app/services/meta_ads_service.py").read_text()

        assert 'params={"parent_id"' not in source, \
            "Found deprecated params={'parent_id': ...} pattern — use constructor arg instead"
        assert "params={'parent_id'" not in source, \
            "Found deprecated params={'parent_id': ...} pattern — use constructor arg instead"


# ---------------------------------------------------------------------------
# Phase 4 verification tests
# ---------------------------------------------------------------------------


@patch("app.services.meta_ads_service.FacebookSession")
@patch("app.services.meta_ads_service.FacebookAdsApi")
class TestCampaignCreation:
    """Verify campaign creation includes is_adset_budget_sharing_enabled."""

    @patch("app.services.meta_ads_service.AdAccount")
    def test_campaign_includes_budget_sharing_field(self, MockAdAccount, mock_api_cls, mock_session_cls):
        """Bug #1: is_adset_budget_sharing_enabled must be set when budget is at adset level."""
        mock_account = MagicMock()
        mock_campaign_result = MagicMock()
        mock_campaign_result.__getitem__ = MagicMock(return_value="120212...")
        mock_account.create_campaign.return_value = mock_campaign_result
        MockAdAccount.return_value = mock_account

        service = MetaAdsService("test_token")
        service.create_campaign(
            ad_account_id="act_123456789",
            name="Test Campaign",
            objective="OUTCOME_ENGAGEMENT",
            special_ad_categories=[],
            status="PAUSED",
        )

        mock_account.create_campaign.assert_called_once()
        create_params = mock_account.create_campaign.call_args.kwargs.get("params", {})

        assert "is_adset_budget_sharing_enabled" in create_params, \
            "Campaign creation MUST include is_adset_budget_sharing_enabled parameter (Meta API v24+ requirement)"
        assert create_params["is_adset_budget_sharing_enabled"] is False, \
            "is_adset_budget_sharing_enabled should be False for single-adset campaigns"


class TestErrorHandling:
    """Verify full error details are captured, not just the generic message."""

    def test_error_message_includes_subcode(self):
        """Error message must include subcode for diagnosis."""
        from app.services.meta_ads_service import _build_rich_message

        mock_error = MagicMock(spec=FacebookRequestError)
        mock_error.api_error_code.return_value = 100
        mock_error.api_error_subcode.return_value = 4834011
        mock_error.api_error_message.return_value = "Invalid parameter"
        mock_error.api_error_type.return_value = "OAuthException"
        mock_error.body.return_value = {
            "error": {
                "error_user_title": "Must specify True or False for is_adset_budget_sharing_enabled",
                "error_user_msg": "You must specify True or False in is_adset_budget_sharing_enabled field.",
            }
        }

        result = _build_rich_message(mock_error)

        assert "4834011" in result, "Subcode must be in the error message"
        assert "budget_sharing" in result.lower(), "User-facing detail must be included"

    def test_error_message_not_generic(self):
        """Error message must NOT be the useless generic 'An unexpected error occurred'."""
        from app.services.meta_ads_service import _build_rich_message

        mock_error = MagicMock(spec=FacebookRequestError)
        mock_error.api_error_code.return_value = 100
        mock_error.api_error_subcode.return_value = 4834011
        mock_error.api_error_message.return_value = "Invalid parameter"
        mock_error.body.return_value = {
            "error": {
                "error_user_title": "Must specify budget sharing field",
                "error_user_msg": "Detailed explanation here",
            }
        }

        result = _build_rich_message(mock_error)
        assert "unexpected" not in result.lower()

    def test_handle_meta_error_passes_rich_message(self):
        """_handle_meta_error should use the rich message, not just the generic one."""
        from app.services.meta_ads_service import _handle_meta_error

        mock_error = MagicMock(spec=FacebookRequestError)
        mock_error.api_error_code.return_value = 100
        mock_error.api_error_subcode.return_value = 4834011
        mock_error.api_error_message.return_value = "Invalid parameter"
        mock_error.body.return_value = {
            "error": {
                "error_user_title": "Budget sharing required",
                "error_user_msg": "Set is_adset_budget_sharing_enabled",
            }
        }

        with pytest.raises(MetaInvalidParameterError) as exc_info:
            _handle_meta_error(mock_error)

        assert "4834011" in exc_info.value.message
        assert "Budget sharing required" in exc_info.value.message


@patch("app.services.meta_ads_service.FacebookSession")
@patch("app.services.meta_ads_service.FacebookAdsApi")
class TestAdSetCreation:
    """Verify AdSet params use correct types."""

    @patch("app.services.meta_ads_service.MetaLocationResolver")
    @patch("app.services.meta_ads_service.AdAccount")
    def test_daily_budget_is_string(self, MockAdAccount, MockResolver, mock_api_cls, mock_session_cls):
        """Bug #4: Meta API expects daily_budget as string, not integer."""
        mock_account = MagicMock()
        mock_adset_result = MagicMock()
        mock_adset_result.__getitem__ = MagicMock(return_value="adset_123")
        mock_account.create_ad_set.return_value = mock_adset_result
        MockAdAccount.return_value = mock_account

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = ({"countries": ["CO"]}, {"countries": ["CO"]})
        MockResolver.return_value = mock_resolver

        service = MetaAdsService("test_token")
        service.resolve_interest_ids = MagicMock(return_value=[])

        service.create_adset(
            ad_account_id="act_123",
            campaign_id="camp_123",
            name="Test AdSet",
            daily_budget_cents=8000000,
            target_audience={"age_min": 18, "age_max": 35, "locations": ["CO"]},
            page_id="page_123",
            whatsapp_phone_number="+573001234567",
        )

        mock_account.create_ad_set.assert_called_once()
        adset_params = mock_account.create_ad_set.call_args.kwargs.get("params", {})

        budget_value = None
        for key, value in adset_params.items():
            if "daily_budget" in str(key).lower():
                budget_value = value
                break

        assert budget_value is not None, "daily_budget must be in AdSet params"
        assert isinstance(budget_value, str), \
            f"daily_budget must be string, got {type(budget_value).__name__}: {budget_value}"
        assert budget_value == "8000000"


class TestSourceCodePatterns:
    """Static analysis of meta_ads_service.py for known bad patterns."""

    def test_no_missing_budget_sharing_field(self):
        source = Path("app/services/meta_ads_service.py").read_text()
        assert "is_adset_budget_sharing_enabled" in source, \
            "meta_ads_service.py must include is_adset_budget_sharing_enabled in campaign creation"

    def test_budget_sharing_set_to_false(self):
        source = Path("app/services/meta_ads_service.py").read_text()
        assert '"is_adset_budget_sharing_enabled": False' in source or \
               "'is_adset_budget_sharing_enabled': False" in source, \
            "is_adset_budget_sharing_enabled must be explicitly set to False"


class TestAdSetTargeting:
    """Verify targeting includes advantage_audience flag (Meta API v25 requirement, error 100 subcode 1870227)."""

    def test_targeting_includes_advantage_audience(self):
        source = Path("app/services/meta_ads_service.py").read_text()
        assert "advantage_audience" in source, \
            "AdSet targeting must include advantage_audience (Meta API v25 requirement, subcode 1870227)"
        assert "targeting_automation" in source, \
            "AdSet targeting must include targeting_automation dict"

    @patch("app.services.meta_ads_service.MetaLocationResolver")
    @patch("app.services.meta_ads_service.FacebookSession")
    @patch("app.services.meta_ads_service.FacebookAdsApi")
    @patch("app.services.meta_ads_service.AdAccount")
    def test_adset_params_include_targeting_automation(self, MockAdAccount, mock_api_cls, mock_session_cls, MockResolver):
        """AdSet targeting dict sent to Meta must contain targeting_automation.advantage_audience."""
        mock_account = MagicMock()
        mock_adset_result = MagicMock()
        mock_adset_result.__getitem__ = MagicMock(return_value="adset_456")
        mock_account.create_ad_set.return_value = mock_adset_result
        MockAdAccount.return_value = mock_account

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = ({"countries": ["CO"]}, {"countries": ["CO"]})
        MockResolver.return_value = mock_resolver

        service = MetaAdsService("test_token")
        service.resolve_interest_ids = MagicMock(return_value=[])

        service.create_adset(
            ad_account_id="act_123",
            campaign_id="camp_123",
            name="Targeting Test",
            daily_budget_cents=5000,
            target_audience={"age_min": 18, "age_max": 65, "locations": ["CO"]},
            page_id="page_123",
            whatsapp_phone_number="+573001234567",
        )

        adset_params = mock_account.create_ad_set.call_args.kwargs.get("params", {})
        targeting = None
        for key, value in adset_params.items():
            if "targeting" == str(key).lower() or str(key) == "targeting":
                targeting = value
                break

        assert targeting is not None, "targeting must be in AdSet params"
        assert "targeting_automation" in targeting, \
            "targeting must include targeting_automation dict"
        assert targeting["targeting_automation"]["advantage_audience"] == 0, \
            "advantage_audience must be 0 (manual targeting)"
