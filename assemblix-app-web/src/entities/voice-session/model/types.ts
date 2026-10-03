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
  firstAudioMs?: number;
}

export type VoiceTimingStage =
  | "eouMs"
  | "sttFinalMs"
  | "brainFirstTokenMs"
  | "ttsFirstAudioMs"
  | "totalMs"
  | "ttsGapMaxMs";

export interface VoiceSessionTranscriptLine {
  role: "user" | "assistant";
  text: string;
  timings?: VoiceTurnTimings | null;
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
}
