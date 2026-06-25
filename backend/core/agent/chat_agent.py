"""Knowledge base chat agent built on pydantic-ai.

The agent gets a fixed system prompt and one tool: search_knowledge,
backed by the hybrid retriever. The model instance is injected so tests
can use TestModel and the API layer can build a cloud model from settings.
"""

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

SYSTEM_PROMPT = (
    "You are Memento, an assistant for a personal video knowledge base. "
    "Answer in the same language as the user. When a question concerns "
    "stored video content, call search_knowledge first and ground your "
    "answer in the returned excerpts. If nothing relevant is found, say so.\n\n"
    "## Citation Rules (MANDATORY)\n\n"
    "Every claim grounded in search results MUST include a clickable timestamp link. "
    "This is not optional.\n\n"
    "### Search Result Format\n"
    "Each result contains: [title] [video_id: XXX] [MM:SS] text\n"
    "- video_id: the platform video identifier (e.g., BV1xx411c7XD or 7123456789012345678)\n"
    "- start_timestamp: the timestamp in MM:SS or H:MM:SS format — use this EXACTLY, do NOT invent or modify timestamps\n\n"
    "### Link Format (REQUIRED for every citation)\n"
    "- Bilibili: [MM:SS description](memento://play?platform=bilibili&video_id=VIDEO_ID&t=SECONDS)\n"
    "- Douyin: [description](memento://play?platform=douyin&video_id=VIDEO_ID)\n\n"
    "### Rules\n"
    "1. ALWAYS use the exact start_timestamp from search results. NEVER invent, combine, or modify timestamps.\n"
    "2. Convert MM:SS to total seconds for the t= parameter (e.g., 5:30 → t=330, 1:23:45 → t=5025).\n"
    "3. video_id starting with 'BV' → platform=bilibili. Long number → platform=douyin.\n"
    "4. For Douyin: do NOT include t= parameter.\n"
    "5. If video_id is null in the search result, you may cite in plain text — but this is rare.\n\n"
    "### Example\n"
    "Search result: [React Hooks tutorial] [video_id: BV1234567890] [05:30] \"useState allows...\"\n"
    "Your response: \"According to [05:30 useState introduction](memento://play?"
    "platform=bilibili&video_id=BV1234567890&t=330), useState allows...\"\n\n"
    "WRONG (do NOT do this): citing as [00:48-01:36], citing without a link, inventing timestamps."
)


@dataclass
class ChatDeps:
    retriever: object  # HybridRetriever-compatible: async search(query, *, top_k)
    top_k: int


def build_agent(model) -> Agent:
    """Build the chat agent around an injected pydantic-ai model."""
    agent = Agent(model, deps_type=ChatDeps, system_prompt=SYSTEM_PROMPT)

    @agent.tool
    async def search_knowledge(ctx: RunContext[ChatDeps], query: str) -> str:
        """Search the video knowledge base and return matching excerpts."""
        results = await ctx.deps.retriever.search(query, top_k=ctx.deps.top_k)
        if not results:
            return "No matching knowledge found."
        return "\n\n".join(
            f"[{result.title_path}]"
            + (f" [video_id: {result.video_id}]" if result.video_id else "")
            + (f" [{result.start_timestamp}]" if result.start_timestamp else "")
            + f"\n{result.text}"
            for result in results
        )

    return agent
