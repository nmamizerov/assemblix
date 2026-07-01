import { CredentialType } from "../model/types";

/**
 * Map an LLM provider name (the stable id served by `/api/llm/providers`)
 * to the matching credential type. Used by the credential picker on the
 * agent-node form to filter user credentials to the right kind.
 *
 * Kept narrow on purpose — providers without a matching `CredentialType`
 * (e.g. `anthropic`, currently absent on the frontend enum) fall through
 * to `undefined` and the picker simply hides itself.
 */
const PROVIDER_TO_CREDENTIAL_TYPE: Record<string, CredentialType> = {
  openai: CredentialType.OPENAI_TOKEN,
  gemini: CredentialType.GEMINI_TOKEN,
  deepseek: CredentialType.DEEPSEEK_TOKEN,
};

export const getCredentialTypeForProvider = (
  providerName: string,
): CredentialType | undefined => PROVIDER_TO_CREDENTIAL_TYPE[providerName];
