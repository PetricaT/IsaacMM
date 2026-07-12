"""Desktop notification wrapper using notify-py."""

from __future__ import annotations

import os

from . import config, paths


def send_notification(title: str, message: str) -> bool:
    if not config.notifications_enabled:
        return False
    try:
        from notifypy import Notify

        notification = Notify(
            default_notification_application_name="IsaacMM",
        )
        notification.title = title
        notification.message = message
        icon = os.path.join(paths.BASE_DIR, "assets", "icon.png")
        if os.path.isfile(icon):
            notification.icon = icon
        notification.send(block=False)
        return True
    except ImportError:
        return False
    except Exception:
        return False
