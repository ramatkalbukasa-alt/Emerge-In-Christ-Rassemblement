import asyncio
import os
import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from channels.testing import WebsocketCommunicator
from channels_redis.core import RedisChannelLayer
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from redis.exceptions import ConnectionError, TimeoutError as RedisTimeoutError

from apps.accounts.models import UserProfile
from apps.churches.models import ChurchExtension, Currency
from apps.reports.consumers import ReportEventsConsumer
from apps.reports.models import ServiceReport


class RealtimeConfigurationTests(SimpleTestCase):
    def test_read_timeout_exceeds_channels_blocking_timeout(self):
        settings_file = Path(__file__).resolve().parents[2] / "ecclessia_manager/settings.py"
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}):
            config = runpy.run_path(str(settings_file))["CHANNEL_LAYERS"]["default"]["CONFIG"]
        layer = RedisChannelLayer(**config)
        self.assertGreater(layer.hosts[0]["socket_timeout"], layer.brpop_timeout)
        self.assertEqual(layer.hosts[0]["socket_connect_timeout"], 5)

    async def test_receive_timeout_closes_socket_without_unhandled_exception(self):
        fail = asyncio.Event()
        async def receive_event(*args):
            await fail.wait()
            raise RedisTimeoutError("simulated")
        layer = SimpleNamespace(new_channel=AsyncMock(return_value="test.channel"),
                                receive=receive_event, group_add=AsyncMock(), group_discard=AsyncMock())
        with patch("channels.consumer.get_channel_layer", return_value=layer):
            socket = WebsocketCommunicator(ReportEventsConsumer.as_asgi(), "/ws/reports/")
            socket.scope["user"] = SimpleNamespace(is_authenticated=True)
            connected, _ = await socket.connect()
            self.assertTrue(connected)
            with self.assertLogs("apps.reports.consumers", level="WARNING"):
                fail.set()
                self.assertEqual(await socket.receive_output(), {"type": "websocket.close", "code": 1013})
                await socket.wait()

    async def test_cleanup_failure_does_not_break_disconnect(self):
        consumer = ReportEventsConsumer()
        consumer.channel_name = "test.channel"
        consumer.channel_layer = SimpleNamespace(group_discard=AsyncMock(side_effect=ConnectionError("simulated")))
        with self.assertLogs("apps.reports.consumers", level="WARNING"):
            await consumer.disconnect(1000)


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ReportPersistenceDuringRedisOutageTests(TestCase):
    def test_create_commits_report_before_failed_notification(self):
        currency = Currency.objects.get(code="USD")
        extension = ChurchExtension.objects.create(name="Realtime test", slug="realtime-test", currency=currency)
        user = User.objects.create_user(username="realtime-admin")
        UserProfile.objects.create(user=user, role=UserProfile.Role.ADMIN)
        self.client.force_login(user)
        data = {"extension": extension.pk, "currency": currency.pk, "service_date": "2026-09-25", "service_type": "week"}
        for field in ["papa_count", "maman_count", "brothers_count", "sisters_count", "children_count", "offering_regular", "offering_preacher", "offering_tithe", "offering_thanksgiving"]:
            data[field] = 0
        for prefix in ["expenses", "newcomers", "converts", "income_lines"]:
            data[prefix + "-TOTAL_FORMS"] = 0
            data[prefix + "-INITIAL_FORMS"] = 0
        layer = SimpleNamespace(group_send=AsyncMock(side_effect=RedisTimeoutError("simulated")))
        with patch("apps.reports.realtime.get_channel_layer", return_value=layer), patch("apps.notifications.email_service.send_report_submitted_email"):
            with self.assertLogs("apps.reports.realtime", level="WARNING"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(reverse("reports:create"), data)
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(ServiceReport.objects.count(), 1)
                    layer.group_send.assert_not_awaited()
            self.assertEqual(ServiceReport.objects.count(), 1)
            layer.group_send.assert_awaited_once()
