import type { CreateVoiceAgentRequest, VoiceAgentDraft } from "../model/types";

export interface DraftValidation {
  isValid: boolean;
  errors: Partial<Record<keyof VoiceAgentDraft, string>>;
}

// The backend rejects a config whose provider/model pair has no conversation
// route, so a fresh draft must already carry a usable one.
export const DEFAULT_PROVIDER = "openai";
export const DEFAULT_MODEL = "gpt-realtime-2.1";

// Working set of conversation languages. Labels are endonyms (the language's
// own name for itself) so they need no translation — only the field label does.
export const LANGUAGE_OPTIONS: { code: string; label: string }[] = [
  { code: "ru", label: "Русский" },
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "de", label: "Deutsch" },
  { code: "fr", label: "Français" },
  { code: "it", label: "Italiano" },
  { code: "pt", label: "Português" },
  { code: "pl", label: "Polski" },
  { code: "tr", label: "Türkçe" },
  { code: "nl", label: "Nederlands" },
  { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" },
  { code: "zh", label: "中文" },
  { code: "ar", label: "العربية" },
  { code: "hi", label: "हिन्दी" },
];

export const emptyDraft = (): VoiceAgentDraft => ({
  name: "",
  description: "",
  systemPrompt: "",
  firstMessage: "",
  language: "ru",
  provider: DEFAULT_PROVIDER,
  model: DEFAULT_MODEL,
  voiceId: "",
  knowledgeBaseIds: [],
  turnWorkflowId: "",
  finalWorkflowId: "",
  credentialId: null,
  params: {},
});

// Values are i18n keys, not copy — the component resolves them via t().
export const validateDraft = (draft: VoiceAgentDraft): DraftValidation => {
  const errors: DraftValidation["errors"] = {};

  if (!draft.name.trim()) errors.name = "voiceAgents.errors.nameRequired";
  if (!draft.systemPrompt.trim()) errors.systemPrompt = "voiceAgents.errors.promptRequired";
  if (!draft.provider) errors.provider = "voiceAgents.errors.providerRequired";
  if (!draft.model) errors.model = "voiceAgents.errors.modelRequired";

  return { isValid: Object.keys(errors).length === 0, errors };
};

export const applyProviderChange = (
  draft: VoiceAgentDraft,
  provider: string
): VoiceAgentDraft => {
  if (provider === draft.provider) return draft;
  // A credential is provider-specific: leaving one behind on a switched
  // provider is either a hard 400 or a silent fall-back to the system key.
  return { ...draft, provider, model: "", voiceId: "", credentialId: null };
};

export const toCreateRequest = (
  draft: VoiceAgentDraft,
  projectId: string
): CreateVoiceAgentRequest => ({
  projectId,
  name: draft.name,
  description: draft.description || null,
  config: {
    instructions: [{ role: "system", content: draft.systemPrompt }],
    knowledgeBaseIds: draft.knowledgeBaseIds,
    firstMessage: draft.firstMessage || null,
    language: draft.language,
    voice: {
      provider: draft.provider,
      model: draft.model,
      voiceId: draft.voiceId || null,
      credentialId: draft.credentialId,
      realtime: false,
    },
    params: draft.params,
    turnWorkflowId: draft.turnWorkflowId || null,
    finalWorkflowId: draft.finalWorkflowId || null,
  },
});
