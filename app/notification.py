import rumps


def send_notification(title: str, message: str, subtitle: str = "") -> None:
    rumps.notification(
        title=title,
        subtitle=subtitle,
        message=message,
    )
