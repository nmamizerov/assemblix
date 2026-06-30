// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useEffect, useState, useMemo } from "react";
import { useGetPaymentStatusQuery } from "../api/billing.api";
import type { PaymentStatusResponse } from "../model/types";

interface UsePaymentPollingResult {
  status: "loading" | "success" | "error" | "timeout";
  paymentData: PaymentStatusResponse | null;
  isPolling: boolean;
}

const POLL_INTERVAL_MS = 2000; // 2 секунды
const MAX_ATTEMPTS = 30; // 60 секунд всего

export const usePaymentPolling = (
  paymentId: string | null
): UsePaymentPollingResult => {
  const [attempts, setAttempts] = useState(0);

  // Вычисляем статус и shouldPoll на основе данных
  const { status, shouldPoll } = useMemo(() => {
    // Нет paymentId - сразу ошибка
    if (!paymentId) {
      return { status: "error" as const, shouldPoll: false };
    }

    // Превышен таймаут
    if (attempts >= MAX_ATTEMPTS) {
      return { status: "timeout" as const, shouldPoll: false };
    }

    // Начальное состояние - загрузка
    return { status: "loading" as const, shouldPoll: true };
  }, [paymentId, attempts]);

  // Запрашиваем статус платежа
  const {
    data: paymentData,
    isLoading,
    isError,
  } = useGetPaymentStatusQuery(paymentId!, {
    skip: !paymentId || !shouldPoll,
    pollingInterval: shouldPoll ? POLL_INTERVAL_MS : 0,
  });

  // Вычисляем финальный статус на основе ответа API
  const finalStatus = useMemo(() => {
    // Если базовый статус не loading, возвращаем его
    if (status !== "loading") {
      return status;
    }

    // Проверяем ошибку запроса
    if (isError) {
      return "error" as const;
    }

    // Проверяем статус платежа
    if (paymentData) {
      if (paymentData.status === "confirmed") {
        return "success" as const;
      }
      if (paymentData.status === "rejected") {
        return "error" as const;
      }
    }

    return "loading" as const;
  }, [status, isError, paymentData]);

  // Останавливаем поллинг при финальных статусах
  const isPolling = useMemo(() => {
    return (
      shouldPoll &&
      !isLoading &&
      finalStatus === "loading"
    );
  }, [shouldPoll, isLoading, finalStatus]);

  // Счетчик попыток
  useEffect(() => {
    if (!isPolling) return;

    const timer = setInterval(() => {
      setAttempts((prev) => prev + 1);
    }, POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [isPolling]);

  return {
    status: finalStatus,
    paymentData: paymentData || null,
    isPolling,
  };
};