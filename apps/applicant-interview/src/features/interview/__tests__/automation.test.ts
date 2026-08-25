import { describe, expect, it } from "vitest";

import { automatedAnswerProfile } from "../automation";

describe("automated interview answer profiles", () => {
  it("keeps existing modes standard and isolates the entry-level profile", () => {
    expect(automatedAnswerProfile("fast")).toBe("standard");
    expect(automatedAnswerProfile("speech")).toBe("standard");
    expect(automatedAnswerProfile("entry-low")).toBe("entry_low");
  });
});
