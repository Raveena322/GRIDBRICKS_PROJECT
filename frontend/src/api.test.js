import { describe, expect, it } from "vitest";
import { validateDateRange } from "./api";

describe("validateDateRange", () => {
  it("accepts dates inside January 2026", () => {
    expect(validateDateRange("2026-01-01", "2026-01-31")).toBeNull();
  });

  it("rejects inverted ranges", () => {
    expect(validateDateRange("2026-01-10", "2026-01-02")).toMatch(/on or before/i);
  });

  it("rejects dates outside the assignment window", () => {
    expect(validateDateRange("2025-12-31", "2026-01-02")).toMatch(/between/i);
  });

  it("rejects impossible calendar dates", () => {
    expect(validateDateRange("2026-02-30", "2026-02-30")).toMatch(/between/i);
  });
});
