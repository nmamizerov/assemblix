/** m:ss — a call is a phone call, not a stopwatch reading. */
export const formatDuration = (seconds: number): string => {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  return `${minutes}:${String(total % 60).padStart(2, "0")}`;
};

/**
 * Credits are fractions of a cent per call, so the usual 2-decimal money format
 * would render every call as "0.00". Show enough digits to see the number move.
 */
export const formatCredits = (credits: number): string =>
  credits === 0 ? "0" : credits.toFixed(credits < 0.01 ? 5 : 2);
