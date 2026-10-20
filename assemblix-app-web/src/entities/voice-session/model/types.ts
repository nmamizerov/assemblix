export interface VoiceSession {
  id: string;
  voiceAgentId: string;
  clientId: string | null;
  status: "active" | "completed" | "failed";
  startedAt: string;
  endedAt: string | null;
  durationSec: number;
  totalCredits: number;
  ownKeyCostUsd: number;
  turnCount: number;
  endReason: string | null;
}

/** Cascade stage durations (ms) of the turn an assistant line ended. */
export interface VoiceTurnTimings {
  eouMs?: number;
  sttFinalMs?: number;
  brainFirstTokenMs?: number;
  ttsFirstAudioMs?: number;
  totalMs?: number;
  /** Longest silence between audio chunks inside the reply. */
  ttsGapMaxMs?: number;
  /** Silence at the start of the reply audio, before speech is audible. */
  ttsLeadingSilenceMs?: number;
  /** When speech is actually heard: ttsFirstAudioMs + lead-in silence. */
  ttsFirstAudibleMs?: number;
  firstAudioMs?: number;
  /** Smart Turn's last completion probability before the turn ended. */
  smartTurnProb?: number;
  smartTurnAsks?: number;
  /** The reply started during the pause; STT and LLM are then the waits left after it. */
  speculative?: boolean;
  /** LLM time hidden inside the pause by a speculative reply. */
  llmOverlapMs?: number;
}

export type VoiceTimingStage =
  | "eouMs"
  | "sttFinalMs"
  | "brainFirstTokenMs"
  | "ttsFirstAudioMs"
  | "totalMs"
  | "ttsGapMaxMs"
  | "ttsLeadingSilenceMs"
  | "ttsFirstAudibleMs"
  | "llmOverlapMs";

export interface VoiceLlmMessage {
  role: "user" | "assistant";
  content: string;
}

export type VoiceLlmOutcome =
  | "ok"
  | "cancelled"
  | "brain_timeout"
  | "brain_failed"
  | "speculative_discarded";

/** One cascade brain call: what was sent to the LLM and what came back. */
export interface VoiceLlmCall {
  provider: string | null;
  model: string | null;
  effectiveModel: string | null;
  params: Record<string, unknown>;
  /** System instructions excluded — they are the same for every turn. */
  messages: VoiceLlmMessage[];
  response: string;
  inputTokens: number;
  outputTokens: number;
  cachedInputTokens: number | null;
  costUsd: number;
  ttftMs: number | null;
  durationMs: number | null;
  outcome: VoiceLlmOutcome | string;
  error: string | null;
}

/** What one cascade turn spent per stage. */
export interface VoiceTurnUsage {
  sttSeconds: number | null;
  /** STT is billed per stream in 15 s units, so a single turn's share is an estimate. */
  sttCostUsdEstimate: number | null;
  llmCostUsd: number | null;
  ttsChars: number | null;
  ttsCostUsd: number | null;
}

export interface VoiceSessionTranscriptLine {
  role: "user" | "assistant";
  text: string;
  timings?: VoiceTurnTimings | null;
  llmCall?: VoiceLlmCall | null;
  usage?: VoiceTurnUsage | null;
}

export interface VoiceStageConfig {
  provider: string | null;
  model: string | null;
}

export interface VoiceStageCosts {
  sttSeconds: number | null;
  sttCostUsd: number | null;
  llmCostUsd: number | null;
  ttsChars: number | null;
  ttsCostUsd: number | null;
  platformFeeCredits: number | null;
  providerMarginCredits: number | null;
}

/** What a cascade call ran with, stored once per call. */
export interface VoiceCallDetails {
  instructions: string;
  stt: VoiceStageConfig | null;
  brain: (VoiceStageConfig & { params: Record<string, unknown>; historyTurns: number | null }) | null;
  tts: VoiceStageConfig | null;
  costs: VoiceStageCosts | null;
}

/** One analysis-hook run started by the call. */
export interface VoiceSessionExecution {
  id: string;
  workflowId: string;
  status: string;
  startedAt: string | null;
  totalCredits: number;
  ownKeyCostUsd?: number | null;
}

export interface VoiceSessionDetail extends VoiceSession {
  transcript: VoiceSessionTranscriptLine[];
  inputTokens: number;
  outputTokens: number;
  executions: VoiceSessionExecution[];
  timingSummary?: Partial<Record<VoiceTimingStage, { p50: number; p95: number }>> | null;
  callDetails?: VoiceCallDetails | null;
}
