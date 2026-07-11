export interface AvatarTalkStream {
  chunk(text: string): void;
  end(): void;
}

export interface AvatarRenderer {
  connect(sessionToken: string, videoEl: HTMLVideoElement): Promise<void>;
  speak(): AvatarTalkStream;
  disconnect(): void;
}
