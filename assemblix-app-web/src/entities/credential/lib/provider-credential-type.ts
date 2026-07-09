import { CredentialType } from "../model/types";

/**
 * Map a provider name (the stable id served by `/api/llm/providers` for LLM
 * providers, or `/api/voice/providers` for voice providers) to the matching
 * credential type. Used by the credential picker on the agent-node,
 * start-node (voice input), and end-node (voice output) forms to filter user
 * credentials to the right kind.
 *
 * Kept narrow on purpose — providers without a matching `CredentialType`
 * (e.g. `anthropic`, currently absent on the frontend enum) fall through
 * to `undefined` and the picker simply hides itself.
 */
const PROVIDER_TO_CREDENTIAL_TYPE: Record<string, CredentialType> = {
  openai: CredentialType.OPENAI_TOKEN,
  gemini: CredentialType.GEMINI_TOKEN,
  deepseek: CredentialType.DEEPSEEK_TOKEN,
  // Voice (TTS) provider — used by the END-node voice-output credential picker.
  elevenlabs: CredentialType.ELEVENLABS_TOKEN,
  // Avatar provider — used by the AGENT-node avatar-output credential picker.
  anam: CredentialType.ANAM_TOKEN,
  // Voice provider (TTS + STT) — used by both voice-input and voice-output pickers.
  yandex: CredentialType.YANDEX_SPEECHKIT_TOKEN,
};

export const getCredentialTypeForProvider = (
  providerName: string,
): CredentialType | undefined => PROVIDER_TO_CREDENTIAL_TYPE[providerName];
