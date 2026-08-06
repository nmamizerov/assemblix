import type { CreateVoiceAgentRequest, VoiceAgentDraft } from "../model/types";

export interface DraftValidation {
  isValid: boolean;
  errors: Partial<Record<keyof VoiceAgentDraft, string>>;
}

export const emptyDraft = (): VoiceAgentDraft => ({
  name: "",
  description: "",
  systemPrompt: "",
  firstMessage: "",
  language: "ru",
  provider: "",
  model: "",
  voiceId: "",
  knowledgeBaseIds: [],
  turnWorkflowId: "",
  finalWorkflowId: "",
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
  return { ...draft, provider, model: "", voiceId: "" };
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
      credentialId: null,
      realtime: false,
    },
    params: {},
    turnWorkflowId: draft.turnWorkflowId || null,
    finalWorkflowId: draft.finalWorkflowId || null,
  },
});
