"""Why an avatar could not join a call; ``reason`` is what the client is told."""


class AvatarError(Exception):
    reason = "avatar_unavailable"


class AvatarBusy(AvatarError):
    """The vendor refused a new session: its concurrency limit is reached."""

    reason = "avatar_busy"


class AvatarUnavailable(AvatarError):
    reason = "avatar_unavailable"
