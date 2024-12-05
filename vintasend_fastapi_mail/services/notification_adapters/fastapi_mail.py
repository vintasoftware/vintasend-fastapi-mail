from typing import TYPE_CHECKING, Generic, TypeVar

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

from vintasend.constants import NotificationTypes

from vintasend.services.dataclasses import Notification
from vintasend.services.notification_backends.asyncio_base import AsyncIOBaseNotificationBackend
from vintasend.services.notification_adapters.asyncio_base import AsyncIOBaseNotificationAdapter
from vintasend.services.notification_template_renderers.base_templated_email_renderer import BaseTemplatedEmailRenderer
from vintasend.app_settings import NotificationSettings


if TYPE_CHECKING:
    from vintasend.services.notification_service import NotificationContextDict


B = TypeVar("B", bound=AsyncIOBaseNotificationBackend)
T = TypeVar("T", bound=BaseTemplatedEmailRenderer)

class FastAPIMailNotificationAdapter(Generic[B, T], AsyncIOBaseNotificationAdapter[B, T]):
    notification_type = NotificationTypes.EMAIL
    config: ConnectionConfig
    fm: FastMail

    def __init__(
        self, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fm = FastMail(self.config)

    async def send(
        self,
        notification: Notification,
        context: "NotificationContextDict",
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Send the notification to the user through email.

        :param notification: The notification to send.
        :param context: The context to render the notification templates.
        """
        notification_settings = NotificationSettings()

        user_email = await self.backend.get_user_email_from_notification(notification.id)
        to = [user_email]
        bcc = [email for email in notification_settings.NOTIFICATION_DEFAULT_BCC_EMAILS] or []

        context_with_base_url: "NotificationContextDict" = context.copy()
        context_with_base_url["base_url"] = f"{notification_settings.NOTIFICATION_DEFAULT_BASE_URL_PROTOCOL}://{notification_settings.NOTIFICATION_DEFAULT_BASE_URL_DOMAIN}"

        template = self.template_renderer.render(notification, context_with_base_url)

        message = MessageSchema(
            subject=template.subject.strip(),
            recipients=to,
            body=template.body,
            subtype="html",
            bcc=bcc,
            headers=headers,
        )
        await self.fm.send_message(message)
