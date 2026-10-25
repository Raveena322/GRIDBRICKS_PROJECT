const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export const ANALYSIS_MIN = "2026-01-01";
export const ANALYSIS_MAX = "2026-01-31";

export function validateDateRange(from, to) {
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  if (!iso.test(from) || !iso.test(to)) {
    return "Dates must use YYYY-MM-DD.";
  }
  if (from > to) {
    return "Start date must be on or before end date.";
  }
  if (from < ANALYSIS_MIN || to > ANALYSIS_MAX) {
    return `Dates must fall between ${ANALYSIS_MIN} and ${ANALYSIS_MAX}.`;
  }
  return null;
}

export async function fetchAnalysis({ from, to, refresh = false, signal }) {
  const params = new URLSearchParams({ from, to });
  if (refresh) params.set("refresh", "true");
  const response = await fetch(`${API_BASE}/api/analysis?${params.toString()}`, {
    signal,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      body.error ||
      `The analysis API returned HTTP ${response.status}. No dashboard values were invented.`;
    const error = new Error(message);
    error.details = body.details;
    error.status = response.status;
    throw error;
  }
  return body;
}
