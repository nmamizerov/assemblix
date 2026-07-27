export interface AvatarAudioStream {
  // A base64-encoded PCM chunk (pcm_s16le, 16 kHz, mono) to lip-sync to.
  chunk(base64Pcm: string): void;
  end(): void;
}

export interface AvatarRenderer {
  connect(sessionToken: string, videoEl: HTMLVideoElement): Promise<void>;
  // Opens an audio-passthrough stream: the avatar lip-syncs to (and plays) the PCM we push.
  speak(): AvatarAudioStream;
  disconnect(): void;
}
