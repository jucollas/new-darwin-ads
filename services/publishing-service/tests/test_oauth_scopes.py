import re
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.services.meta_exceptions import MetaApiError


REQUIRED_SCOPES = {
    "ads_management",
    "ads_read",
    "business_management",
    "pages_manage_ads",
    "pages_read_engagement",
    "pages_show_list",
    "whatsapp_business_management",
    "whatsapp_business_messaging",
}


class TestOAuthScopes:
    """Verify OAuth flow requests all required scopes including WhatsApp."""

    def test_oauth_scopes_constant_includes_whatsapp(self):
        from app.services.meta_oauth_service import OAUTH_SCOPES
        scopes = set(OAUTH_SCOPES.split(","))
        assert "whatsapp_business_management" in scopes
        assert "whatsapp_business_messaging" in scopes

    def test_all_required_scopes_present_in_constant(self):
        from app.services.meta_oauth_service import OAUTH_SCOPES
        scopes = set(OAUTH_SCOPES.split(","))
        missing = REQUIRED_SCOPES - scopes
        assert not missing, f"Missing scopes in OAUTH_SCOPES: {missing}"

    def test_login_url_contains_whatsapp_scopes(self):
        from app.services.meta_oauth_service import MetaOAuthService
        service = MetaOAuthService()
        url = service.generate_login_url(state="test_state")
        assert "whatsapp_business_management" in url
        assert "whatsapp_business_messaging" in url

    def test_source_files_have_no_stale_scope_strings(self):
        """Scan all Python files for scope strings and ensure none are missing WhatsApp scopes."""
        service_dir = Path("services/publishing-service")
        if not service_dir.exists():
            service_dir = Path(".")

        for py_file in service_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or "test_" in py_file.name:
                continue
            content = py_file.read_text()
            scope_matches = re.findall(
                r'(?:OAUTH_SCOPES|scope|SCOPE)[s]?\s*=\s*["\']([^"\']+)["\']',
                content,
            )
            for scope_string in scope_matches:
                if "ads_management" not in scope_string:
                    continue  # Not an OAuth scope string
                scopes = set(scope_string.split(","))
                missing = REQUIRED_SCOPES - scopes
                assert not missing, (
                    f"Missing scopes in {py_file.name}: {missing}"
                )


class TestOrphanCleanup:
    """Verify orphan campaigns are cleaned up on failure."""

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_campaign_deleted_when_adset_fails(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_celery,
    ):
        """If AdSet creation fails, the orphan Campaign in Meta should be deleted."""
        mock_fetch.return_value = {
            "copy_text": "Buy shoes!",
            "image_url": "https://storage.googleapis.com/test/image.png",
            "target_audience": {"age_min": 25, "age_max": 35, "locations": ["CO"]},
            "whatsapp_number": "+573001234567",
        }
        mock_decrypt.return_value = "decrypted_token"

        mock_service = MagicMock()
        mock_service.upload_image.return_value = "hash_123"
        mock_service.create_campaign.return_value = "camp_orphan_123"
        mock_service.create_adset.side_effect = MetaApiError(
            "WhatsApp phone number is not linked", error_code=100
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

        # Orphan campaign should have been cleaned up
        mock_service.delete_campaign.assert_called_once_with("camp_orphan_123")

        # Publication should be marked as failed
        calls = mock_update_pub.call_args_list
        failed_call = [c for c in calls if len(c.args) >= 2 and c.args[1] == "failed"]
        assert len(failed_call) > 0

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_no_cleanup_when_campaign_not_yet_created(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_celery,
    ):
        """If failure happens before campaign creation (e.g. image upload), no cleanup needed."""
        mock_fetch.return_value = {
            "copy_text": "text", "image_url": "http://img.png",
            "target_audience": {}, "whatsapp_number": "+573001234567",
        }
        mock_decrypt.return_value = "token"

        mock_service = MagicMock()
        mock_service.upload_image.side_effect = MetaApiError(
            "Image upload failed", error_code=100
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

        # No campaign was created, so delete_campaign should NOT be called
        mock_service.delete_campaign.assert_not_called()

    @patch("app.tasks.celery_tasks.celery_app")
    @patch("app.tasks.celery_tasks._update_campaign_status")
    @patch("app.tasks.celery_tasks._update_publication_status")
    @patch("app.tasks.celery_tasks._fetch_proposal")
    @patch("app.tasks.celery_tasks.MetaAdsService")
    @patch("app.tasks.celery_tasks.decrypt_token")
    def test_cleanup_failure_does_not_mask_original_error(
        self, mock_decrypt, mock_service_cls, mock_fetch, mock_update_pub,
        mock_update_camp, mock_celery,
    ):
        """If cleanup itself fails, the original error should still be reported."""
        mock_fetch.return_value = {
            "copy_text": "text", "image_url": "http://img.png",
            "target_audience": {}, "whatsapp_number": "+573001234567",
        }
        mock_decrypt.return_value = "token"

        mock_service = MagicMock()
        mock_service.upload_image.return_value = "hash_123"
        mock_service.create_campaign.return_value = "camp_123"
        mock_service.create_adset.side_effect = MetaApiError(
            "AdSet creation failed", error_code=100
        )
        mock_service.delete_campaign.side_effect = Exception("Cleanup also failed")
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
            # Should NOT raise — cleanup failure is swallowed
            publish_ad_task(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
                "00000000-0000-0000-0000-000000000004",
            )

        # Original error should still be reported
        calls = mock_update_pub.call_args_list
        failed_call = [c for c in calls if len(c.args) >= 2 and c.args[1] == "failed"]
        assert len(failed_call) > 0
        error_msg = failed_call[0].kwargs.get("error_message", "")
        assert "AdSet creation failed" in error_msg
