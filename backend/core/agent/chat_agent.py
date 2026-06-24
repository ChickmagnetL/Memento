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
    "## Timestamp Link Format\n\n"
    "When referencing video content with specific timestamps from search results, "
    "generate clickable links using the memento:// protocol:\n\n"
    "**Format:**\n"
    "- Bilibili: [MM:SS description](memento://play?platform=bilibili&video_id=BV1xx411c7XD&t=SECONDS)\n"
    "- Douyin: [description](memento://play?platform=douyin&video_id=7123456789012345678)\n\n"
    "**Platform Detection:**\n"
    "- video_id starting with 'BV' → platform=bilibili\n"
    "- video_id that is a long number (typically 19 digits) → platform=douyin\n\n"
    "**Timestamp Handling:**\n"
    "- For Bilibili: Always include the &t=SECONDS parameter for timestamp navigation\n"
    "- Convert MM:SS or H:MM:SS format to total seconds (e.g., 5:30 → t=330, 1:23:45 → t=5025)\n"
    "- For Douyin: Do NOT include t parameter, and note: \"(Douyin does not support "
    "timestamp navigation, please drag progress bar manually)\"\n\n"
    "**Example:**\n"
    "Search result: [React Hooks tutorial] [05:30] \"useState allows...\"\n"
    "Your response: \"According to [05:30 useState introduction](memento://play?"
    "platform=bilibili&video_id=BV1234567890&t=330), useState allows...\"\n\n"
    "**Important:**\n"
    "- Only generate memento:// links when video_id is provided in search results\n"
    "- If video_id is null or missing, cite timestamps in plain text format like [05:30]\n"
    "- Use the video_id from search results exactly as provided\n"
    "- Use the start_timestamp from search results to calculate seconds for t parameter\n"
    "- Always use the memento:// protocol for video links, never use plain timestamps"
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
