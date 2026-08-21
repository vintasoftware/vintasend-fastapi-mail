from typing import TYPE_CHECKING, Generic, TypeVar

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from vintasend.app_settings import NotificationSettings
from vintasend.constants import NotificationTypes
from vintasend.services.dataclasses import Notification, OneOffNotification
from vintasend.services.notification_adapters.asyncio_base import AsyncIOBaseNotificationAdapter
from vintasend.services.notification_backends.asyncio_base import AsyncIOBaseNotificationBackend
from vintasend.services.notification_template_renderers.base_templated_email_renderer import (
    BaseTemplatedEmailRenderer,
)


if TYPE_CHECKING:
    from vintasend.services.dataclasses import NotificationContextDict


B = TypeVar("B", bound=AsyncIOBaseNotificationBackend)
T = TypeVar("T", bound=BaseTemplatedEmailRenderer)


class FastAPIMailNotificationAdapter(Generic[B, T], AsyncIOBaseNotificationAdapter[B, T]):  # noqa: UP046
    notification_type = NotificationTypes.EMAIL
    config: ConnectionConfig
    fm: FastMail

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fm = FastMail(self.config)

    async def send(
        self,
        notification: "Notification | OneOffNotification",
        context: "NotificationContextDict",
        headers: dict[str, str] | None = None,
    ) -> None:
        """
        Send the notification to the user through email.

        :param notification: The notification to send (regular or one-off).
        :param context: The context to render the notification templates.
        """
        notification_settings = NotificationSettings()

        to: list[str] = [await self._get_recipient_email(notification)]
        bcc: list[str] = list(notification_settings.NOTIFICATION_DEFAULT_BCC_EMAILS)

        context_with_base_url: "NotificationContextDict" = context.copy()
        context_with_base_url["base_url"] = (
            f"{notification_settings.NOTIFICATION_DEFAULT_BASE_URL_PROTOCOL}://{notification_settings.NOTIFICATION_DEFAULT_BASE_URL_DOMAIN}"
        )

        template = self.template_renderer.render(notification, context_with_base_url)

        message = MessageSchema(
            subject=template.subject.strip(),
            recipients=to,
            body=template.body,
            subtype=MessageType.html,
            bcc=bcc,
            headers=headers,
        )
        await self.fm.send_message(message)

    async def _get_recipient_email(self, notification: "Notification | OneOffNotification") -> str:
        """Resolve the destination address for either notification flavour.

        A one-off notification carries the address on itself; a regular one only knows the
        user, so the backend has to look it up.
        """
        if isinstance(notification, OneOffNotification):
            return notification.email_or_phone
        return await self.backend.get_user_email_from_notification(notification.id)
