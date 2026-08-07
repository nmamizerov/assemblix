"""Realtime runtime for Voice Agents.

Unlike the rest of the backend this package is not request/response: a voice
session is a long-lived asyncio task owning two sockets (the browser and the
provider). It is deliberately kept out of the 4-layer stack — see the
"Realtime runtime" section in CLAUDE.md for its constraints.
"""
