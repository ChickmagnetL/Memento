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
    "answer in the returned excerpts. Cite source timestamps like [02:35] "
    "when the excerpts provide them. If nothing relevant is found, say so."
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
            + (f" [{result.start_timestamp}]" if result.start_timestamp else "")
            + f"\n{result.text}"
            for result in results
        )

    return agent
