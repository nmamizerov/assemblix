# Where `costPerMinute` comes from

`costPerMinute` on a `conversation` model is what one wall-clock minute of a
realtime call costs **us**, at the provider's list price, before any margin. It is
the only cost input to voice billing: `compute_session_credits` multiplies it by the
call's duration and adds the platform fee on top (see
`services/voice_session_service.py`).

The number is a derived figure, not a published one — providers bill realtime audio
per *token*, and a minute of conversation is a token count only under an assumption
about how the minute is spent. This file records that assumption and the rates it was
applied to, so a figure can be re-derived when provider pricing moves.

## The conversion

Providers that publish per-token audio rates are converted with two constants:

| | tokens per minute of audio |
|---|---|
| input (the caller speaking) | 600 |
| output (the agent speaking) | 1200 |

and one traffic assumption — **full input, half output**: the microphone is open for
the whole call, so input is billed for every minute; the agent speaks for roughly half
of it, so output is billed for half.

```
cost_per_minute = 600 × input_$/1M ÷ 1e6  +  0.5 × 1200 × output_$/1M ÷ 1e6
```

The mix is a deliberate under- rather than over-statement of agent talk time: a call
where the agent talks more than half the time costs us more than this line says, and
the 10% margin plus the always-charged `$0.02/min` platform fee absorb that.

## The figures

Verified against the providers' published pricing on 2026-08-18.

### `gpt-realtime-2.1` — $0.0576/min

Published audio rates: **input $32.00 / 1M tokens, output $64.00 / 1M tokens**.

```
input   600 × 32 / 1e6          = $0.0192
output  0.5 × 1200 × 64 / 1e6   = $0.0384
                                  --------
                                  $0.0576
```

Source: <https://developers.openai.com/api/docs/pricing>

### `gpt-realtime-2.1-mini` — $0.018/min

Published audio rates: **input $10.00 / 1M tokens, output $20.00 / 1M tokens**.

```
input   600 × 10 / 1e6          = $0.006
output  0.5 × 1200 × 20 / 1e6   = $0.012
                                  --------
                                  $0.018
```

Source: <https://developers.openai.com/api/docs/pricing>

### `gemini-3.1-flash-live-preview` — $0.014/min

Google publishes per-minute audio rates directly, so the token conversion above does
not apply — only the full-input/half-output mix does: **input $0.005/min, output
$0.018/min**.

```
input   0.005                   = $0.005
output  0.5 × 0.018             = $0.009
                                  --------
                                  $0.014
```

Source: <https://ai.google.dev/gemini-api/docs/pricing>

## Changing a figure

Re-run the arithmetic above against the provider's current published rate and update
both the JSON and the corresponding block here in the same commit. Do not change one
without the other — a bare literal with no derivation is what this file exists to
prevent. Past charges are unaffected: every voice ledger row stamps
`credit_value_usd` and `margin_multiplier` into its metadata, so a historical charge
stays re-derivable after a reprice.

`costPerMinute` also appears on `transcription` models (e.g. `whisper-1`), where it is
the provider's own published per-minute price and needs no derivation.
