import type { VoiceOutputConfig } from "@/entities/voice-model";
import type {
  CreateVoiceAgentRequest,
  VoiceAgent,
  VoiceAgentCascadeConfig,
  VoiceAgentConfig,
  VoiceAgentDraft,
  VoiceAgentMode,
} from "../model/types";
import { defaultSystemPrompt, isDefaultSystemPrompt } from "./default-prompts";

export type DraftErrorField =
  | keyof VoiceAgentDraft
  | "brainModel"
  | "historyTurns"
  | "minSilenceMs"
  | "maxSilenceMs"
  | "smartTurnThreshold"
  | "prerollMs";

export interface DraftValidation {
  isValid: boolean;
  errors: Partial<Record<DraftErrorField, string>>;
}

// The backend rejects a config whose provider/model pair has no conversation
// route, so a fresh draft must already carry a usable one.
export const DEFAULT_PROVIDER = "openai";
export const DEFAULT_MODEL = "gpt-realtime-2.1";

// Brain providers the cascade accepts (backend `AgentProvider`).
export const BRAIN_PROVIDERS = ["openai", "gemini", "deepseek"];
export const DEFAULT_BRAIN_PROVIDER = "gemini";
export const DEFAULT_BRAIN_MODEL = "gemini-3.1-flash-lite";
// What `voiceBrainDefaults` yields for the default brain model.
export const DEFAULT_BRAIN_PARAMS = { thinking_level: "minimal", max_tokens: 300 };

// Cheapest streaming synthesis route with a Russian voice.
export const DEFAULT_CASCADE_TTS: VoiceOutputConfig = {
  provider: "yandex",
  model: "yandex-tts-v3-chunk",
  voiceId: "alena",
  credentialId: null,
  realtime: true,
};

// Mirrors the backend TurnConfig / PromptBrainConfig bounds.
export const CASCADE_LIMITS = {
  minSilenceMs: { min: 64, max: 2000 },
  maxSilenceMs: { min: 200, max: 5000 },
  prerollMs: { min: 0, max: 1000 },
  historyTurns: { min: 2, max: 400 },
} as const;

export const defaultCascade = (): VoiceAgentCascadeConfig => ({
  stt: { provider: "yandex", model: "general", credentialId: null },
  turn: {
    minSilenceMs: 200,
    maxSilenceMs: 1500,
    smartTurn: true,
    smartTurnThreshold: 0.5,
    prerollMs: 300,
    speculative: true,
  },
  brain: {
    type: "prompt",
    provider: DEFAULT_BRAIN_PROVIDER,
    model: DEFAULT_BRAIN_MODEL,
    credentialId: null,
    params: { ...DEFAULT_BRAIN_PARAMS },
    historyTurns: 40,
  },
});

// Only OpenAI exposes custom voices: an id created through its /v1/audio/voices
// endpoint is accepted wherever a built-in voice name is. Those ids live in the
// customer's own account, so no catalog can list them and the field has to accept
// free text. Gemini Live has prebuilt voices only — there, free text would just
// produce a call that fails at connect time.
export const supportsCustomVoices = (provider: string): boolean =>
  provider === "openai";

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
  mode: "realtime",
  systemPrompt: defaultSystemPrompt("ru"),
  firstMessage: "",
  language: "ru",
  provider: DEFAULT_PROVIDER,
  model: DEFAULT_MODEL,
  voiceId: "",
  knowledgeBaseIds: [],
  turnWorkflowId: "",
  finalWorkflowId: "",
  credentialId: null,
  tts: null,
  avatar: null,
  params: {},
  cascade: defaultCascade(),
  extraConfig: {},
  ttsBeforeCascade: null,
});

const KNOWN_CONFIG_KEYS = new Set([
  "instructions",
  "knowledgeBaseIds",
  "firstMessage",
  "language",
  "mode",
  "voice",
  "tts",
  "cascade",
  "avatar",
  "params",
  "turnWorkflowId",
  "finalWorkflowId",
]);

const cascadeFromConfig = (
  cascade: VoiceAgentConfig["cascade"]
): VoiceAgentCascadeConfig => {
  const defaults = defaultCascade();
  if (!cascade) return defaults;
  return {
    ...cascade,
    stt: { ...defaults.stt, ...cascade.stt },
    turn: { ...defaults.turn, ...cascade.turn },
    // Saved params stay as they were: voice defaults are for new brains only.
    brain: {
      ...defaults.brain,
      ...cascade.brain,
      params: cascade.brain?.params ?? {},
    },
  };
};

export const draftFromVoiceAgent = (voiceAgent: VoiceAgent): VoiceAgentDraft => {
  const { config } = voiceAgent;
  const systemPrompt =
    config.instructions.find((instruction) => instruction.role === "system")
      ?.content ?? "";
  const extraConfig = Object.fromEntries(
    Object.entries(config).filter(([key]) => !KNOWN_CONFIG_KEYS.has(key))
  );

  return {
    ...emptyDraft(),
    name: voiceAgent.name,
    description: voiceAgent.description ?? "",
    mode: config.mode ?? "realtime",
    systemPrompt,
    firstMessage: config.firstMessage ?? "",
    language: config.language,
    provider: config.voice?.provider ?? "",
    model: config.voice?.model ?? "",
    voiceId: config.voice?.voiceId ?? "",
    knowledgeBaseIds: config.knowledgeBaseIds,
    turnWorkflowId: config.turnWorkflowId ?? "",
    finalWorkflowId: config.finalWorkflowId ?? "",
    credentialId: config.voice?.credentialId ?? null,
    tts: config.tts ?? null,
    avatar: config.avatar ?? null,
    params: config.params,
    cascade: cascadeFromConfig(config.cascade),
    extraConfig,
  };
};

/** What the agent runs on, for headers and list cards. */
export const describeVoiceAgentModel = (
  config: Pick<VoiceAgentConfig, "mode" | "voice" | "cascade">
): { mode: VoiceAgentMode; provider: string; model: string } => {
  if (config.mode === "cascade" && config.cascade) {
    return {
      mode: "cascade",
      provider: config.cascade.brain.provider,
      model: config.cascade.brain.model,
    };
  }
  return {
    mode: "realtime",
    provider: config.voice?.provider ?? "",
    model: config.voice?.model ?? "",
  };
};

const inRange = (value: number, { min, max }: { min: number; max: number }) =>
  Number.isFinite(value) && value >= min && value <= max;

// Values are i18n keys, not copy — the component resolves them via t().
export const validateDraft = (draft: VoiceAgentDraft): DraftValidation => {
  const errors: DraftValidation["errors"] = {};

  if (!draft.name.trim()) errors.name = "voiceAgents.errors.nameRequired";
  if (!draft.systemPrompt.trim()) errors.systemPrompt = "voiceAgents.errors.promptRequired";
  if (draft.mode === "realtime") {
    if (!draft.provider) errors.provider = "voiceAgents.errors.providerRequired";
    if (!draft.model) errors.model = "voiceAgents.errors.modelRequired";
  } else {
    const { brain, turn } = draft.cascade;
    if (!draft.tts?.provider || !draft.tts.model) {
      errors.tts = "voiceAgents.errors.ttsRequired";
    }
    if (!brain.provider || !brain.model) {
      errors.brainModel = "voiceAgents.errors.brainModelRequired";
    }
    if (!Number.isInteger(brain.historyTurns) || !inRange(brain.historyTurns, CASCADE_LIMITS.historyTurns)) {
      errors.historyTurns = "voiceAgents.errors.historyTurnsRange";
    }
    if (!inRange(turn.minSilenceMs, CASCADE_LIMITS.minSilenceMs)) {
      errors.minSilenceMs = "voiceAgents.errors.minSilenceRange";
    }
    if (!inRange(turn.maxSilenceMs, CASCADE_LIMITS.maxSilenceMs)) {
      errors.maxSilenceMs = "voiceAgents.errors.maxSilenceRange";
    } else if (turn.maxSilenceMs < turn.minSilenceMs) {
      errors.maxSilenceMs = "voiceAgents.errors.maxSilenceBelowMin";
    }
    // The threshold is unused (and its field disabled) without smart turn.
    if (
      turn.smartTurn &&
      (!Number.isFinite(turn.smartTurnThreshold) ||
      turn.smartTurnThreshold <= 0 ||
        turn.smartTurnThreshold >= 1)
    ) {
      errors.smartTurnThreshold = "voiceAgents.errors.smartTurnThresholdRange";
    }
    if (!inRange(turn.prerollMs, CASCADE_LIMITS.prerollMs)) {
      errors.prerollMs = "voiceAgents.errors.prerollRange";
    }
  }

  // An enabled-but-incomplete avatar would otherwise only fail on save with a
  // backend 400 — catch it here alongside the other required fields.
  if (
    draft.avatar !== null &&
    (!draft.avatar.provider ||
      !draft.avatar.avatarModel ||
      !draft.avatar.credentialId ||
      !draft.avatar.avatarId)
  ) {
    errors.avatar = "voiceAgents.errors.avatarIncomplete";
  }

  return { isValid: Object.keys(errors).length === 0, errors };
};

export const applyLanguageChange = (
  draft: VoiceAgentDraft,
  language: string
): VoiceAgentDraft => {
  if (language === draft.language) return draft;
  const systemPrompt = isDefaultSystemPrompt(draft.systemPrompt)
    ? defaultSystemPrompt(language)
    : draft.systemPrompt;
  return { ...draft, language, systemPrompt };
};

export const applyProviderChange = (
  draft: VoiceAgentDraft,
  provider: string
): VoiceAgentDraft => {
  if (provider === draft.provider) return draft;
  // A credential is provider-specific: leaving one behind on a switched
  // provider is either a hard 400 or a silent fall-back to the system key.
  // `tts` is deliberately kept: it belongs to the voice, not to the model.
  return { ...draft, provider, model: "", voiceId: "", credentialId: null };
};

// A streaming voice can speak a cascade; a batch-only one cannot.
const isStreamingTts = (tts: VoiceOutputConfig | null): boolean =>
  Boolean(tts && tts.realtime === true && tts.provider && tts.model);

/**
 * `canUseExternalVoice` says whether the realtime model can answer in text.
 * Leaving cascade restores the realtime voice the draft had before, unless the
 * user changed the cascade voice and the realtime model can still use it.
 */
export const applyModeChange = (
  draft: VoiceAgentDraft,
  mode: VoiceAgentMode,
  canUseExternalVoice = false
): VoiceAgentDraft => {
  if (mode === draft.mode) return draft;

  if (mode === "cascade") {
    const tts = isStreamingTts(draft.tts) ? draft.tts : { ...DEFAULT_CASCADE_TTS };
    return {
      ...draft,
      mode,
      tts,
      ttsBeforeCascade: { previous: draft.tts, applied: tts },
    };
  }

  const stash = draft.ttsBeforeCascade;
  const isUntouched = stash !== null && draft.tts === stash.applied;
  let tts: VoiceOutputConfig | null;
  if (canUseExternalVoice && !isUntouched) tts = draft.tts;
  else if (stash) tts = stash.previous;
  else tts = canUseExternalVoice ? draft.tts : null;
  return { ...draft, mode, tts, ttsBeforeCascade: null };
};

export const applyBrainProviderChange = (
  draft: VoiceAgentDraft,
  provider: string
): VoiceAgentDraft => {
  const { brain } = draft.cascade;
  if (provider === brain.provider) return draft;
  // Model ids, credentials and tunables are all provider-specific.
  return {
    ...draft,
    cascade: {
      ...draft.cascade,
      brain: { ...brain, provider, model: "", credentialId: null, params: {} },
    },
  };
};

export const toCreateRequest = (
  draft: VoiceAgentDraft,
  projectId: string
): CreateVoiceAgentRequest => ({
  projectId,
  name: draft.name,
  description: draft.description || null,
  config: {
    ...draft.extraConfig,
    mode: draft.mode,
    instructions: [{ role: "system", content: draft.systemPrompt }],
    knowledgeBaseIds: draft.knowledgeBaseIds,
    firstMessage: draft.firstMessage || null,
    language: draft.language,
    voice:
      draft.mode === "cascade"
        ? null
        : {
            provider: draft.provider,
            model: draft.model,
            voiceId: draft.voiceId || null,
            credentialId: draft.credentialId,
            realtime: false,
          },
    tts: draft.tts,
    cascade: draft.mode === "cascade" ? draft.cascade : null,
    avatar: draft.avatar,
    params: draft.params,
    turnWorkflowId: draft.turnWorkflowId || null,
    finalWorkflowId: draft.finalWorkflowId || null,
  },
});
