export interface VoiceSession {
  id: string;
  voiceAgentId: string;
  status: "active" | "completed" | "failed";
  startedAt: string;
  endedAt: string | null;
  durationSec: number;
  totalCredits: number;
  turnCount: number;
  endReason: string | null;
}

export interface VoiceSessionTranscriptLine {
  role: "user" | "assistant";
  text: string;
}

/** One analysis-hook run started by the call. */
export interface VoiceSessionExecution {
  id: string;
  workflowId: string;
  status: string;
  startedAt: string | null;
  totalCredits: number;
}

export interface VoiceSessionDetail extends VoiceSession {
  transcript: VoiceSessionTranscriptLine[];
  inputTokens: number;
  outputTokens: number;
  executions: VoiceSessionExecution[];
}
