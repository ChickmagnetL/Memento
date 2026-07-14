"""Knowledge base chat agent built on pydantic-ai.

The agent gets a fixed system prompt and one tool: search_knowledge,
backed by the hybrid retriever. The model instance is injected so tests
can use TestModel and the API layer can build a cloud model from settings.
"""

import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from core.rag.embedding import EmbeddingError

SYSTEM_PROMPT = (
    "You are Memento, an assistant for a personal video knowledge base. "
    "Answer in the same language as the user. When a question concerns "
    "stored video content, call search_knowledge first and ground your "
    "answer in the returned excerpts. If nothing relevant is found, say so.\n\n"
    "## Tool Routing\n"
    "- Questions about the user themselves (what they're learning, their "
    "preferences, background, weak spots) → answer from the user memory "
    "block; do NOT call search_knowledge for these.\n"
    "- Specific or detail questions (a particular point, timestamp, snippet) "
    "→ call search_knowledge.\n"
    "- Summary, overview, or exploration questions (\"what does this video cover\", "
    "\"summarize\", \"which videos discuss X\") → first call lookup_documents to see "
    "relevant documents, then call summarize_document(doc_id) on the chosen one.\n"
    "- You do NOT see all documents by default; lookup_documents gives you the "
    "global view. Do not assume search_knowledge results are the whole story.\n\n"
    "## Citation Rules (MANDATORY)\n\n"
    "Every claim grounded in search results MUST include a clickable timestamp link. "
    "This is not optional.\n\n"
    "### Search Result Format\n"
    "Each result contains: [title] [platform: PLATFORM] [video_id: XXX] [MM:SS] text\n"
    "- platform: the exact source platform (bilibili, douyin, or youtube)\n"
    "- video_id: the source platform's video identifier\n"
    "- start_timestamp: the timestamp in MM:SS or H:MM:SS format — use this EXACTLY, do NOT invent or modify timestamps\n\n"
    "### Link Format (REQUIRED for every citation)\n"
    "- Bilibili: [MM:SS description](memento://play?platform=bilibili&video_id=VIDEO_ID&t=SECONDS)\n"
    "- Douyin: [description](memento://play?platform=douyin&video_id=VIDEO_ID)\n"
    "- YouTube: [MM:SS description](memento://play?platform=youtube&video_id=VIDEO_ID&t=SECONDS)\n\n"
    "### Rules\n"
    "1. ALWAYS use the exact start_timestamp from search results. NEVER invent, combine, or modify timestamps.\n"
    "2. Convert MM:SS to total seconds for the t= parameter (e.g., 5:30 → t=330, 1:23:45 → t=5025).\n"
    "3. Use the exact platform field from the search result. NEVER infer a platform from video_id.\n"
    "4. For Douyin: do NOT include t= parameter.\n"
    "5. If platform or video_id is null, cite in plain text instead of creating a memento link.\n\n"
    "### Example\n"
    "Search result: [React Hooks tutorial] [platform: bilibili] [video_id: BV1234567890] [05:30] \"useState allows...\"\n"
    "Your response: \"According to [05:30 useState introduction](memento://play?"
    "platform=bilibili&video_id=BV1234567890&t=330), useState allows...\"\n\n"
    "WRONG (do NOT do this): citing as [00:48-01:36], citing without a link, inventing timestamps."
    "\n\n### Tool Failure Rules\n"
    "If a tool says knowledge base retrieval is currently unavailable because "
    "the embedding model is unavailable, tell the user this plainly. Do not "
    "cite stored video content and do not fabricate timestamp links."
)

MEMORY_BLOCK_TEMPLATE = (
    "\n\n<user_memory>\n"
    "This section holds facts remembered about the user across sessions "
    "(learning profile, preferences, background). When the user asks about "
    "THEMSELVES — what they are learning, their preferences, background, or "
    "weak spots — answer from this section FIRST. Do NOT call "
    "search_knowledge for questions about the user; those answers live here, "
    "not in the video knowledge base.\n"
    "\n{items}\n"
    "</user_memory>\n"
)

EMBEDDING_UNAVAILABLE_TOOL_MESSAGE = (
    "Knowledge base retrieval is currently unavailable because the "
    "embedding model is unavailable. Tell the user that knowledge-base "
    "retrieval is temporarily unavailable, do not cite stored video content, "
    "and do not invent timestamps."
)


def build_system_prompt(memories: list[dict] | None = None) -> str:
    """Assemble the system prompt, optionally injecting a <user_memory> block."""
    prompt = SYSTEM_PROMPT
    if memories:
        items = "\n".join(f"- {m['content']}" for m in memories)
        prompt += MEMORY_BLOCK_TEMPLATE.format(items=items)
    return prompt


@dataclass
class ChatDeps:
    retriever: object  # HybridRetriever-compatible: async search(query, *, top_k)
    top_k: int
    summary_store: object = None   # DocumentSummaryStore-compatible
    embedder: object = None        # embedding client with .embed(list[str]) -> list[list[float]]


def history_from_pairs(pairs: list[tuple[str, str]]) -> list:
    """Rebuild pydantic-ai message_history from (role, content) text pairs.

    'user' -> ModelRequest with a UserPromptPart.
    'assistant' -> ModelResponse with a TextPart.
    Any other role is skipped (defensive — only user/assistant stored in P1).
    """
    history: list = []
    for role, content in pairs:
        if role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            history.append(ModelResponse(parts=[TextPart(content=content)]))
    return history


def build_agent(model, system_prompt: str | None = None) -> Agent:
    """Build the chat agent around an injected pydantic-ai model.

    Args:
        model: The pydantic-ai model instance.
        system_prompt: Optional custom system prompt. When None, uses SYSTEM_PROMPT.
    """
    agent = Agent(model, deps_type=ChatDeps, system_prompt=system_prompt or SYSTEM_PROMPT)

    @agent.tool
    async def search_knowledge(ctx: RunContext[ChatDeps], query: str) -> str:
        """Search the video knowledge base and return matching excerpts."""
        try:
            results = await ctx.deps.retriever.search(query, top_k=ctx.deps.top_k)
        except EmbeddingError:
            return EMBEDDING_UNAVAILABLE_TOOL_MESSAGE
        if not results:
            return "No matching knowledge found."
        return "\n\n".join(
            f"[{result.title_path}]"
            + (f" [platform: {result.platform}]" if result.platform else "")
            + (f" [video_id: {result.video_id}]" if result.video_id else "")
            + (f" [{result.start_timestamp}]" if result.start_timestamp else "")
            + f"\n{result.text}"
            for result in results
        )

    @agent.tool
    async def lookup_documents(ctx: RunContext[ChatDeps], query: str) -> str:
        """List documents whose topic matches the query. Use for summary/overview
        questions to see what documents exist before summarizing. Returns top-K
        lines with [doc_id, title, brief]."""
        try:
            vectors = await asyncio.to_thread(ctx.deps.embedder.embed, [query])
            briefs = ctx.deps.summary_store.search_briefs(
                query_vector=vectors[0], top_k=ctx.deps.top_k
            )
        except EmbeddingError:
            return EMBEDDING_UNAVAILABLE_TOOL_MESSAGE
        if not briefs:
            return "No matching documents found."
        lines = []
        for entry in briefs:
            payload = entry.get("payload") or {}
            doc_id = payload.get("document_id", "")
            title = payload.get("title", "")
            brief = payload.get("brief", "")
            lines.append(f"[doc_id: {doc_id}] {title} — {brief}")
        return "\n".join(lines)

    @agent.tool
    async def summarize_document(ctx: RunContext[ChatDeps], doc_id: str) -> str:
        """Return the full summary of one document. Use after lookup_documents
        to get a document's overview. doc_id comes from lookup_documents."""
        try:
            l2, _l3 = await ctx.deps.summary_store.get_or_generate(doc_id)
        except ValueError:
            return f"Document {doc_id} not found."
        except EmbeddingError:
            return EMBEDDING_UNAVAILABLE_TOOL_MESSAGE
        return l2

    @agent.tool
    async def propose_memory(ctx: RunContext[ChatDeps], content: str) -> str:
        """Propose a memory to remember about the user (learning profile/preference).
        Call ONLY when the user reveals a stable cross-session fact about themselves
        (what they're learning, weak spots, explanation-style preferences, background).
        Do NOT call for one-off or time-sensitive info. The user will be asked to
        confirm; you do not write anything. At most once per turn."""
        return f"[memory proposed, awaiting user confirmation]: {content}"

    return agent
