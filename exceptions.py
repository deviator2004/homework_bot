class NotSendingMessageError(Exception):
    """Исключения, не требующие отправки сообщения в Telegram."""

    pass


class Error404(Exception):
    """Исключение при сбое доступа к API."""

    pass


class UnexpectedStatusError(Exception):
    """Исключение при неожиданном статусе."""

    pass
