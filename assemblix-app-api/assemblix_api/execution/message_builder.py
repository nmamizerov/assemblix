# /execution/message_builder.py
"""Building the LLM message list from instructions + knowledge base + chat history.

Extracted from `AgentNode._build_messages` without changing behavior. Returns the
combined OpenAI format (system instructions + KB + history). The agent node delegates
here, and before the Pydantic AI call it splits the result into system instructions
and the dialog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from assemblix_api.schemas.execution import ExecutionContext
    from assemblix_api.schemas.node import AgentInstruction


class MessageBuilder:
    async def build(
        self,
        *,
        instructions: list[AgentInstruction],
        knowledge_base_ids: list[str] | None,
        include_chat_history: bool,
        context: ExecutionContext,
        node_data: dict,
    ) -> list[dict]:
        messages: list[dict] = []

        # 1. Knowledge base content (if configured).
        kb_content = ""
        if knowledge_base_ids and context.knowledge_base_service:
            kb_ids = [UUID(kb_id) for kb_id in knowledge_base_ids]
            kb_content = await context.knowledge_base_service.get_combined_content(kb_ids)

        # 2. System instructions with CEL rendering; KB is injected into the first system instruction.
        kb_injected = False
        for instruction in instructions:
            content = context.templates.render(instruction.content, context, node_data)

            if kb_content and instruction.role == "system" and not kb_injected:
                content = f"{content}\n\n---\nБаза знаний:\n{kb_content}\n---"
                kb_injected = True

            messages.append({"role": instruction.role, "content": content})

        # If there was no system instruction — add the KB as a separate system message.
        if kb_content and not kb_injected:
            messages.insert(0, {"role": "system", "content": f"База знаний:\n{kb_content}"})

        # 3. Dialog history from in-memory chat_history.
        # chat_history is never empty: the preparation phase always puts the current
        # user message there (even for a non-session run — there it is the only
        # element). For a session, past turns are added as well.
        if include_chat_history:
            messages.extend(context.chat_history)
        else:
            # include_chat_history=False means "do not mix in past correspondence,
            # only the current question". We take the last user message — that is the
            # current turn (iterating from the end in case of a trailing assistant).
            for msg in reversed(context.chat_history):
                if msg.get("role") == "user":
                    messages.append(msg)
                    break

        return messages
