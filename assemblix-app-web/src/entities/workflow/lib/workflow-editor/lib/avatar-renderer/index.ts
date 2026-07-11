import { createAnamRenderer } from "./anam-renderer";

import type { AvatarRenderer } from "./types";

export type { AvatarRenderer, AvatarTalkStream } from "./types";

export const createRenderer = (provider: string): AvatarRenderer => {
  if (provider === "anam") return createAnamRenderer();
  throw new Error(`Unsupported avatar provider: ${provider}`);
};
