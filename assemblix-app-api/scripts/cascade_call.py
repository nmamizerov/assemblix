"""Place a cascade call from a WAV file and print per-turn timings.

Usage:
  uv run python scripts/cascade_call.py --api http://localhost:8000 \
      --key <project API key> --agent <voice agent id> --wav sample.wav [--tail 6]

The WAV must be 16 kHz mono PCM16. Audio is streamed in real time, then silence for
``--tail`` seconds so the agent can answer; the agent's audio is discarded.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import wave

import httpx
import websockets

_CHUNK_MS = 20


async def _call(args: argparse.Namespace) -> None:
    async with httpx.AsyncClient(base_url=args.api, timeout=10) as http:
        response = await http.post(
            f"/api/voice-agents/{args.agent}/sessions",
            headers={"Authorization": f"Bearer {args.key}"},
            json={},
        )
        response.raise_for_status()
        token = response.json()["token"]

    with wave.open(args.wav, "rb") as wav:
        if wav.getframerate() != 16000 or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise SystemExit("WAV must be 16 kHz mono PCM16")
        pcm = wav.readframes(wav.getnframes())

    url = args.api.replace("http", "ws", 1) + f"/api/voice-agents/sessions/{token}/stream"
    chunk = 16000 * 2 * _CHUNK_MS // 1000
    async with websockets.connect(url, max_size=None) as ws:

        async def listen() -> None:
            async for message in ws:
                if isinstance(message, bytes):
                    continue
                event = json.loads(message)
                if event.get("type") in ("turn.timings", "error", "session.closed"):
                    print(json.dumps(event, ensure_ascii=False))
                elif event.get("type") == "transcript" and event.get("isFinal"):
                    print(f"{event['role']}: {event['text']}")

        listener = asyncio.create_task(listen())
        silence = b"\x00" * chunk
        for offset in range(0, len(pcm), chunk):
            await ws.send(pcm[offset : offset + chunk])
            await asyncio.sleep(_CHUNK_MS / 1000)
        for _ in range(int(args.tail * 1000 / _CHUNK_MS)):
            await ws.send(silence)
            await asyncio.sleep(_CHUNK_MS / 1000)
        await ws.send(json.dumps({"type": "session.stop"}))
        await asyncio.sleep(1)
        listener.cancel()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--key", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--tail", type=float, default=6.0)
    asyncio.run(_call(parser.parse_args()))


if __name__ == "__main__":
    main()
