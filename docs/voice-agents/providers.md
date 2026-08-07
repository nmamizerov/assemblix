# Providers

Two speech-to-speech providers ship today. They are genuinely different, and the honest
version is that quality and responsiveness pull in opposite directions — there is no
setting that gives you both.

## OpenAI Realtime

The most conversational of the two. Interruption handling is excellent: cut in
mid-sentence and the agent stops immediately and picks up where you took it. Turn
detection is quick and rarely talks over you.

The weakness is non-English audio. Russian in particular is intelligible but audibly
accented, in a way callers notice.

## Gemini Live

Markedly more natural non-English speech, across 70+ languages. If your callers speak
Russian, this is usually the one to try first.

The trade is interruption. Barge-in is handled entirely on Google's side and reported
after the fact, so cutting the agent off is less crisp than with OpenAI — expect it to
finish a word or two more than you would like.

## Choosing

| If you care most about | Choose |
|---|---|
| English conversations that feel natural to interrupt | OpenAI Realtime |
| How the agent sounds in Russian or another non-English language | Gemini Live |

Both are configured the same way and cost is charged the same way — by call duration, at
the per-minute price shown next to the model. Switching is a dropdown; nothing else about
the agent changes.

## Custom voices

**OpenAI** lets you use a voice of your own. You create it once against OpenAI's API —
upload a consent recording from the voice actor, then a sample of up to 30 seconds — and
get back an id like `voice_1234`. Paste that id into the **Voice** field instead of
picking a built-in name, and calls will answer in that voice. The feature is limited to
accounts OpenAI has enabled for it (their sales team gates access), and an organization
may hold at most 20 voices.

**Gemini Live** has prebuilt voices only. Google's voice cloning — Chirp 3: Instant
Custom Voice — is part of Cloud Text-to-Speech, is itself allow-listed, and does not
reach the Live API, so there is nothing to paste here.

This is why the voice field behaves differently between the two: for OpenAI you can type
as well as choose, for Gemini you choose from the list.

## Your own API key

By default a call uses the Assemblix system key. Select a credential in the **Voice**
section to bill the provider directly instead. The credential type has to match the
provider — an OpenAI key for OpenAI, a Gemini key for Gemini.
