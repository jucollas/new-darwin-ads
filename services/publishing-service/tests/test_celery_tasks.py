import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from facebook_business.exceptions import FacebookBadObjectError
from app.services.meta_exceptions import MetaApiError, MetaRateLimitError, MetaTokenInvalidError


class TestPublishAdTask:

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._flag_ad_account_inactive")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_publish_ad_task_success(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_flag, mock_celery,
    ):
        mock_celery.send_task = MagicMock()
        mock_fetch.return_value = {
            "copy_text": "Buy shoes!",
            "image_url": "https://storage.googleapis.com/test/image.png",
            "target_audience": {"age_min": 25, "age_max": 35, "locations": ["CO"]},
            "whatsapp_number": "+573001234567",
            "budget_daily_cents": 5000,
        }
        mock_decrypt.return_value = "decrypted_token"

        mock_service = MagicMock()
        mock_service.upload_image.return_value = "hash_123"
        mock_service.create_campaign.return_value = "camp_123"
        mock_service.create_adset.return_value = ("adset_123", {"countries": ["CO"]})
        mock_service.create_adcreative.return_value = "creative_123"
        mock_service.create_ad.return_value = "ad_123"
        mock_service_cls.return_value = mock_service

        mock_account = MagicMock()
        mock_account.access_token_encrypted = "encrypted"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.meta_page_id = "page_123"
        mock_account.whatsapp_phone_number = "+573001234567"

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_account
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import publish_ad_task
            publish_ad_task(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
                "00000000-0000-0000-0000-000000000004",
                name="Test Campaign",
            )

        pub_id = "00000000-0000-0000-0000-000000000001"
        mock_update_pub.assert_any_call(pub_id, "publishing")
        # Verify incremental saves happened (Bug #2)
        mock_update_pub.assert_any_call(pub_id, "publishing", meta_ids={"meta_image_hash": "hash_123"})
        # Verify final active call includes all IDs and resolved locations
        mock_update_pub.assert_any_call(
            pub_id, "active",
            meta_ids={
                "meta_campaign_id": "camp_123",
                "meta_adset_id": "adset_123",
                "meta_adcreative_id": "creative_123",
                "meta_ad_id": "ad_123",
                "meta_image_hash": "hash_123",
            },
            resolved_geo_locations={"countries": ["CO"]},
        )
        mock_update_camp.assert_called_with("00000000-0000-0000-0000-000000000003", "published")

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._flag_ad_account_inactive")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_publish_ad_task_token_invalid_no_retry(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_flag, mock_celery,
    ):
        mock_fetch.return_value = {
            "copy_text": "text", "image_url": "http://img.png",
            "target_audience": {}, "whatsapp_number": "+573001234567",
        }
        mock_decrypt.return_value = "token"

        mock_service = MagicMock()
        mock_service.upload_image.side_effect = MetaTokenInvalidError(
            "Token expired", error_code=190
        )
        mock_service_cls.return_value = mock_service

        mock_account = MagicMock()
        mock_account.access_token_encrypted = "encrypted"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.meta_page_id = "page_123"
        mock_account.whatsapp_phone_number = "+573001234567"

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_account
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import publish_ad_task
            publish_ad_task(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
                "00000000-0000-0000-0000-000000000004",
            )

        mock_flag.assert_called_once_with("00000000-0000-0000-0000-000000000002")
        mock_update_pub.assert_any_call(
            "00000000-0000-0000-0000-000000000001", "failed",
            error_message="Token expired", error_code=190,
        )
        mock_update_camp.assert_called_with("00000000-0000-0000-0000-000000000003", "failed")

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_publish_ad_task_meta_error_sets_failed(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_celery,
    ):
        mock_fetch.return_value = {
            "copy_text": "text", "image_url": "http://img.png",
            "target_audience": {}, "whatsapp_number": "+573001234567",
        }
        mock_decrypt.return_value = "token"

        mock_service = MagicMock()
        mock_service.upload_image.side_effect = MetaApiError(
            "Invalid param", error_code=100
        )
        mock_service_cls.return_value = mock_service

        mock_account = MagicMock()
        mock_account.access_token_encrypted = "encrypted"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.meta_page_id = "page_123"
        mock_account.whatsapp_phone_number = "+573001234567"

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_account
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import publish_ad_task
            publish_ad_task(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
                "00000000-0000-0000-0000-000000000004",
            )

        mock_update_pub.assert_any_call(
            "00000000-0000-0000-0000-000000000001", "failed",
            error_message="Invalid param", error_code=100,
        )


class TestRefreshTokensTask:

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_refresh_tokens_verifies_all_active_accounts(
        self, mock_decrypt, mock_service_cls, mock_celery,
    ):
        mock_decrypt.return_value = "decrypted"
        mock_service = MagicMock()
        mock_service.verify_token.return_value = {"is_valid": True, "needs_reauth": False}
        mock_service_cls.return_value = mock_service

        mock_account = MagicMock()
        mock_account.is_active = True
        mock_account.id = "acc_1"
        mock_account.user_id = "user_1"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.access_token_encrypted = "encrypted"
        mock_account.token_expires_at = None

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_account]
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import refresh_tokens_task
            result = refresh_tokens_task()

        assert result["total"] == 1
        assert result["flagged"] == 0

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_refresh_tokens_flags_invalid_tokens(
        self, mock_decrypt, mock_service_cls, mock_celery,
    ):
        mock_celery.send_task = MagicMock()
        mock_decrypt.return_value = "decrypted"
        mock_service = MagicMock()
        mock_service.verify_token.return_value = {"is_valid": False, "needs_reauth": True}
        mock_service_cls.return_value = mock_service

        mock_account = MagicMock()
        mock_account.is_active = True
        mock_account.id = "acc_1"
        mock_account.user_id = "user_1"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.access_token_encrypted = "encrypted"
        mock_account.token_expires_at = None

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_account]
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import refresh_tokens_task
            result = refresh_tokens_task()

        assert result["flagged"] == 1
        assert mock_account.is_active is False


class TestPublishTaskWhatsAppValidation:
    """Bug #3: Task must fail immediately if no WhatsApp number is available."""

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_fails_fast_when_no_whatsapp_number(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_celery,
    ):
        """If neither ad_account nor proposal has whatsapp_number, task should fail
        immediately without calling Meta API."""
        mock_fetch.return_value = {
            "copy_text": "text", "image_url": "http://img.png",
            "target_audience": {}, "whatsapp_number": None,
        }
        mock_decrypt.return_value = "token"

        mock_account = MagicMock()
        mock_account.access_token_encrypted = "encrypted"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.meta_page_id = "page_123"
        mock_account.whatsapp_phone_number = None  # No WhatsApp number

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_account
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import publish_ad_task
            publish_ad_task(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
                "00000000-0000-0000-0000-000000000004",
            )

        # MetaAdsService should NEVER be instantiated — no Meta API call attempted
        mock_service_cls.assert_not_called()

        # Publication should be marked as failed with actionable error message
        mock_update_pub.assert_any_call(
            "00000000-0000-0000-0000-000000000001", "failed",
            error_message=pytest.approx(
                "Cannot publish WhatsApp ad: no WhatsApp phone number configured. "
                "Set it via PUT /api/v1/publish/ad-accounts/00000000-0000-0000-0000-000000000002/whatsapp",
                abs=0,
            ),
        )

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_fails_fast_when_whatsapp_is_empty_string(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_celery,
    ):
        """Empty string whatsapp_number should also trigger fail-fast."""
        mock_fetch.return_value = {
            "copy_text": "text", "image_url": "http://img.png",
            "target_audience": {}, "whatsapp_number": "",
        }
        mock_decrypt.return_value = "token"

        mock_account = MagicMock()
        mock_account.access_token_encrypted = "encrypted"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.meta_page_id = "page_123"
        mock_account.whatsapp_phone_number = ""  # Empty string

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_account
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import publish_ad_task
            publish_ad_task(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
                "00000000-0000-0000-0000-000000000004",
            )

        mock_service_cls.assert_not_called()


class TestErrorHandling:
    """Bug #4: FacebookBadObjectError must be caught explicitly, not fall to generic handler."""

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_bad_object_error_stores_specific_message(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_celery,
    ):
        """When SDK raises FacebookBadObjectError, error_message should contain
        'SDK configuration error', not 'unexpected error'."""
        mock_fetch.return_value = {
            "copy_text": "text", "image_url": "http://img.png",
            "target_audience": {}, "whatsapp_number": "+573001234567",
        }
        mock_decrypt.return_value = "token"

        mock_service = MagicMock()
        mock_service.upload_image.side_effect = FacebookBadObjectError("parent_id is None")
        mock_service_cls.return_value = mock_service

        mock_account = MagicMock()
        mock_account.access_token_encrypted = "encrypted"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.meta_page_id = "page_123"
        mock_account.whatsapp_phone_number = "+573001234567"

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_account
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import publish_ad_task
            publish_ad_task(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
                "00000000-0000-0000-0000-000000000004",
            )

        # Should contain "SDK configuration error", not "unexpected error"
        calls = mock_update_pub.call_args_list
        failed_call = [c for c in calls if len(c.args) >= 2 and c.args[1] == "failed"]
        assert len(failed_call) > 0
        error_msg = failed_call[0].kwargs.get("error_message", "")
        assert "SDK configuration error" in error_msg, \
            f"Expected 'SDK configuration error' in message, got: {error_msg}"
        assert "parent_id is None" in error_msg

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_generic_exception_does_not_retry(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_celery,
    ):
        """Bug #5: Generic exceptions must NOT trigger retry."""
        mock_fetch.return_value = {
            "copy_text": "text", "image_url": "http://img.png",
            "target_audience": {}, "whatsapp_number": "+573001234567",
        }
        mock_decrypt.return_value = "token"

        mock_service = MagicMock()
        mock_service.upload_image.side_effect = RuntimeError("Something broke")
        mock_service_cls.return_value = mock_service

        mock_account = MagicMock()
        mock_account.access_token_encrypted = "encrypted"
        mock_account.meta_ad_account_id = "act_123"
        mock_account.meta_page_id = "page_123"
        mock_account.whatsapp_phone_number = "+573001234567"

        with patch("app.tasks.celery_tasks.get_sync_session") as mock_get_session:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_account
            mock_get_session.return_value = mock_db

            from app.tasks.celery_tasks import publish_ad_task
            # Should NOT raise (no retry) — just mark as failed
            publish_ad_task(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
                "00000000-0000-0000-0000-000000000004",
            )

        # Verify publication is marked as failed
        calls = mock_update_pub.call_args_list
        failed_call = [c for c in calls if len(c.args) >= 2 and c.args[1] == "failed"]
        assert len(failed_call) > 0
        error_msg = failed_call[0].kwargs.get("error_message", "")
        assert "Unexpected error" in error_msg
