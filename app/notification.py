import rumps


def send_notification(message: str) -> None:
    rumps.notification(
        title="Listener",
        subtitle="Error",
        message=message,
    )
