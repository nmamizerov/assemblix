/**
 * USD actually spent on the user's own provider keys.
 *
 * A single run is usually fractions of a cent, so the plain 2-decimal money format
 * renders everything as "$0.00" — the same reason `formatCredits` exists. Show
 * enough digits below a cent to see the number move.
 */
export const formatUsd = (usd: number): string => {
  if (!usd) return "$0";
  return usd < 0.01 ? `$${usd.toFixed(5)}` : `$${usd.toFixed(2)}`;
};
