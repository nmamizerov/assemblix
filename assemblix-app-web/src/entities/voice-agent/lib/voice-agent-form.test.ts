import { describe, expect, it } from "vitest";

import {
  applyProviderChange,
  emptyDraft,
  toCreateRequest,
  validateDraft,
} from "./voice-agent-form";

describe("voice agent form", () => {
  it("guides a draft from empty to a valid create request", () => {
    // Arrange
    const draft = emptyDraft();

    // Assert — an empty draft is not submittable
    expect(validateDraft(draft).isValid).toBe(false);
    expect(validateDraft(draft).errors.systemPrompt).toBeDefined();
    expect(validateDraft(draft).errors.name).toBeDefined();

    // Act — fill it in
    const filled = {
      ...draft,
      name: "Receptionist",
      systemPrompt: "You are a clinic receptionist.",
      firstMessage: "Hello",
      language: "ru",
      provider: "openai",
      model: "gpt-realtime-2.1",
      voiceId: "alloy",
      turnWorkflowId: "wf-1",
    };

    // Assert — now valid, and the payload matches the API contract
    expect(validateDraft(filled).isValid).toBe(true);
    expect(toCreateRequest(filled, "proj-1")).toEqual({
      projectId: "proj-1",
      name: "Receptionist",
      description: null,
      config: {
        instructions: [{ role: "system", content: "You are a clinic receptionist." }],
        knowledgeBaseIds: [],
        firstMessage: "Hello",
        language: "ru",
        voice: {
          provider: "openai",
          model: "gpt-realtime-2.1",
          voiceId: "alloy",
          credentialId: null,
          realtime: false,
        },
        params: {},
        turnWorkflowId: "wf-1",
        finalWorkflowId: null,
      },
    });
  });

  it("clears a stale model and voice when the provider changes", () => {
    // Arrange
    const draft = {
      ...emptyDraft(),
      provider: "openai",
      model: "gpt-realtime-2.1",
      voiceId: "alloy",
    };

    // Act
    const switched = applyProviderChange(draft, "gemini");

    // Assert — no cross-provider leftovers
    expect(switched.provider).toBe("gemini");
    expect(switched.model).toBe("");
    expect(switched.voiceId).toBe("");
    expect(validateDraft(switched).errors.model).toBeDefined();

    // Act — re-selecting the same provider is a no-op
    expect(applyProviderChange(draft, "openai")).toEqual(draft);
  });
});
