// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

declare global {
  interface Window {
    Paddle?: {
      Initialize: (config: { token: string; environment?: string }) => void;
      Checkout: {
        open: (config: { transactionId: string }) => void;
      };
    };
  }
}

const PADDLE_SCRIPT_URL = "https://cdn.paddle.com/paddle/v2/paddle.js";

export const initPaddle = (
  clientToken: string,
  environment: "sandbox" | "production" = "production",
): Promise<void> => {
  return new Promise<void>((resolve) => {
    if (window.Paddle) {
      resolve();
      return;
    }

    const script = document.createElement("script");
    script.src = PADDLE_SCRIPT_URL;
    script.async = true;
    script.onload = () => {
      window.Paddle?.Initialize({ token: clientToken, environment });
      resolve();
    };
    document.head.appendChild(script);
  });
};

export const openPaddleCheckout = (transactionId: string) => {
  window.Paddle?.Checkout.open({ transactionId });
};

export const isPaddleEnabled = !!import.meta.env.VITE_PADDLE_CLIENT_TOKEN;