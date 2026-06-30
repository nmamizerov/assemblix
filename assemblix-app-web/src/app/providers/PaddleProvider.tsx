// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useEffect, type ReactNode } from "react";
import { initPaddle, isPaddleEnabled } from "@/shared/lib/paddle";

export const PaddleProvider = ({ children }: { children: ReactNode }) => {
  useEffect(() => {
    if (!isPaddleEnabled) return;

    const token = import.meta.env.VITE_PADDLE_CLIENT_TOKEN as string;
    const environment = (import.meta.env.VITE_PADDLE_ENVIRONMENT as "sandbox" | "production") || "production";

    initPaddle(token, environment);
  }, []);

  return <>{children}</>;
};