import enum
import rumps


class NotificationType(enum.Enum):
    READY = "ready"
    PERMISSION_REQUIRED = "permission_required"
    ERROR = "error"
    PLEASE_WAIT = "please_wait"
    TRANSCRIPTION_COMPLETE = "transcription_complete"
    NO_SPEECH_DETECTED = "no_speech_detected"


_NOTIFICATION_CONFIG: dict[NotificationType, str] = {
    NotificationType.READY: "Ready",
    NotificationType.PERMISSION_REQUIRED: "Permission Required",
    NotificationType.ERROR: "Error",
    NotificationType.PLEASE_WAIT: "Please wait",
    NotificationType.TRANSCRIPTION_COMPLETE: "Transcription complete",
    NotificationType.NO_SPEECH_DETECTED: "No speech detected",
}


def send_notification(notification_type: NotificationType, message: str) -> None:
    subtitle = _NOTIFICATION_CONFIG.get(notification_type)
    if subtitle is None:
        return

    rumps.notification(
        title="Listener",
        subtitle=subtitle,
        message=message,
    )
