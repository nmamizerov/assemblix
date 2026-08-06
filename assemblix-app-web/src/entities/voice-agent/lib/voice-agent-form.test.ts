import { describe, expect, it } from "vitest";

import {
  applyProviderChange,
  DEFAULT_MODEL,
  DEFAULT_PROVIDER,
  emptyDraft,
  toCreateRequest,
  validateDraft,
} from "./voice-agent-form";

describe("voice agent form", () => {
  it("guides a draft from empty to a valid create request", () => {
    // Arrange
    const draft = emptyDraft();

    // Assert — only the fields a user must supply are missing; the seeded
    // provider/model pair is one the backend accepts as a conversation route
    expect(validateDraft(draft).isValid).toBe(false);
    expect(validateDraft(draft).errors.systemPrompt).toBeDefined();
    expect(validateDraft(draft).errors.name).toBeDefined();
    expect(validateDraft(draft).errors.provider).toBeUndefined();
    expect(validateDraft(draft).errors.model).toBeUndefined();
    expect(draft.provider).toBe(DEFAULT_PROVIDER);
    expect(draft.model).toBe(DEFAULT_MODEL);
    expect({ provider: draft.provider, model: draft.model }).toEqual({
      provider: "openai",
      model: "gpt-realtime-2.1",
    });

    // Act — fill it in
    const filled = {
      ...draft,
      name: "Receptionist",
      systemPrompt: "You are a clinic receptionist.",
      firstMessage: "Hello",
      language: "ru",
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

  it("carries config the form does not edit through to the request", () => {
    // Arrange — fields only the API can set today
    const draft = {
      ...emptyDraft(),
      name: "Receptionist",
      systemPrompt: "You are a clinic receptionist.",
      credentialId: "cred-1",
      params: { vadSilenceMs: 500 },
    };

    // Act
    const request = toCreateRequest(draft, "proj-1");

    // Assert — a load → save round trip is lossless
    expect(request.config.voice.credentialId).toBe("cred-1");
    expect(request.config.params).toEqual({ vadSilenceMs: 500 });
  });

  it("clears a stale model and voice when the provider changes", () => {
    // Arrange
    const draft = {
      ...emptyDraft(),
      voiceId: "alloy",
      credentialId: "cred-1",
    };

    // Act
    const switched = applyProviderChange(draft, "gemini");

    // Assert — no cross-provider leftovers
    expect(switched.provider).toBe("gemini");
    expect(switched.model).toBe("");
    expect(switched.voiceId).toBe("");
    expect(switched.credentialId).toBeNull();
    expect(validateDraft(switched).errors.model).toBeDefined();

    // Act — re-selecting the same provider is a no-op
    expect(applyProviderChange(draft, "openai")).toEqual(draft);
  });
});
