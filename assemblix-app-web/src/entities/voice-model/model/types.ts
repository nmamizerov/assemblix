export interface VoiceProviderListItem {
  name: string; // stable id, e.g. "openai"
  label: string; // human label
  modelsCount: number;
}

export type VoiceCapability = "transcription" | "speech" | "realtime" | "conversation";

export interface VoiceModelMetadata {
  id: string;
  label: string;
  description?: string | null;
  capability: VoiceCapability;
  route: "transcription" | "completion" | "speech" | "conversation" | "realtime";
  costPerMinute?: number | null;
  // Conversation models only: whether the model can answer in text instead of
  // audio, which is what an external voice needs in order to speak for it.
  supportsTextOutput?: boolean;
}

export interface VoiceListItem {
  id: string;
  name: string;
  previewUrl?: string;
}

// TTS provider/voice. `provider` is a voice-provider id (e.g. "elevenlabs"),
// intentionally a plain string and not the `Provider` enum (which only covers
// LLM providers).
export interface VoiceOutputConfig {
  provider: string;
  model: string;
  voiceId?: string;
  credentialId?: string;
  // Explicit opt-in to live WS streaming. Only offered for providers that
  // expose a realtime route (e.g. ElevenLabs); ignored/absent otherwise.
  realtime?: boolean;
}
