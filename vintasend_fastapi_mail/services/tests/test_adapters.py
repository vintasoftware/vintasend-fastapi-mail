import uuid
import pytest
import base64
from unittest import IsolatedAsyncioTestCase

from fastapi_mail import ConnectionConfig

from vintasend.constants import NotificationStatus, NotificationTypes
from vintasend.exceptions import (
    NotificationTemplateRenderingError,
)
from vintasend.services.dataclasses import Notification
from vintasend.services.notification_backends.stubs.fake_backend import FakeAsyncIOFileBackend, FakeFileBackend
from vintasend_fastapi_mail.services.notification_adapters.fastapi_mail import FastAPIMailNotificationAdapter



class FastAPIMailNotificationAdapterTestCase(IsolatedAsyncioTestCase):
    def setup_method(self, method) -> None:
        self.config = ConnectionConfig(
            MAIL_USERNAME="test",
            MAIL_PASSWORD="test",  # type: ignore
            MAIL_FROM="foo@example.com",
            MAIL_PORT=587,
            MAIL_SERVER="smtp.example.com",
            MAIL_STARTTLS=False,
            MAIL_SSL_TLS=False,
            TEMPLATE_FOLDER=None,
            SUPPRESS_SEND=True,
        )

        super().setUp()

    def teardown_method(self, method) -> None:
        FakeFileBackend(database_file_name="fastapi-mail-adapter-test-notifications.json").clear()
    
    def teardown_class(self) -> None:
        FakeFileBackend(database_file_name="fastapi-mail-adapter-test-notifications.json").clear()

    def create_notification(self):
        return Notification(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            notification_type=NotificationTypes.EMAIL.value,
            title="Test Notification",
            body_template="Test Body",
            context_name="test_context",
            context_kwargs={"test": "test"},
            send_after=None,
            subject_template="Test Subject",
            preheader_template="Test Preheader",
            status=NotificationStatus.PENDING_SEND.value,
        )

    def create_notification_context(self):
        return {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_send_notification(self):
        notification = self.create_notification()
        context = self.create_notification_context()

        backend = FakeAsyncIOFileBackend(database_file_name="fastapi-mail-adapter-test-notifications.json")
        backend.notifications.append(notification)
        await backend._store_notifications()

        adapter = FastAPIMailNotificationAdapter(
            "vintasend.services.notification_template_renderers.stubs.fake_templated_email_renderer.FakeTemplateRenderer",
            "vintasend.services.notification_backends.stubs.fake_backend.FakeAsyncIOFileBackend",
            backend_kwargs={"database_file_name": "fastapi-mail-adapter-test-notifications.json"},
            config=self.config
        )

        with adapter.fm.record_messages() as outbox:
            await adapter.send(notification, context)

        assert len(outbox) == 1
        email = outbox[0]
        payload = email.get_payload(0).get_payload()
        email_body = base64.b64decode(payload).decode("utf-8")
        assert email["Subject"] == notification.subject_template
        assert email_body == notification.body_template
        assert email["To"] == "testemail@example.com"  # This is the email that the FakeFileBackend returns
        assert email["From"] == "foo@example.com"  # This is the email that the FakeFileBackend returns

    @pytest.mark.asyncio
    async def test_send_notification_with_render_error(self):
        notification = self.create_notification()
        context = self.create_notification_context()

        backend = FakeAsyncIOFileBackend(database_file_name="fastapi-mail-adapter-test-notifications.json")
        backend.notifications.append(notification)
        await backend._store_notifications()

        adapter = FastAPIMailNotificationAdapter(
            "vintasend.services.notification_template_renderers.stubs.fake_templated_email_renderer.FakeTemplateRendererWithException",
            "vintasend.services.notification_backends.stubs.fake_backend.FakeAsyncIOFileBackend",
            backend_kwargs={"database_file_name": "fastapi-mail-adapter-test-notifications.json"},
            config=self.config
        )
        with adapter.fm.record_messages() as outbox:
            with pytest.raises(NotificationTemplateRenderingError):
                await adapter.send(notification, context)

        assert len(outbox) == 0
