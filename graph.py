"""LangGraph agent graph: reasoning node + tools node."""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app_texts import SYSTEM_PROMPT_TEMPLATE
from tools import TOOLS
from utils import (
    get_retrieved_context,
    list_files_internal,
    resolve_target_dir,
    sync_project_to_chroma,
)


def build_graph():
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")

    llm_holder = {
        "model": model_name,
        "client": ChatGoogleGenerativeAI(model=model_name, temperature=0.2).bind_tools(TOOLS),
    }

    def reasoning_node(state: MessagesState):
        latest_user_text = ""
        for message in reversed(state["messages"]):
            if isinstance(message, HumanMessage):
                latest_user_text = str(message.content)
                break

        target_dir = resolve_target_dir(latest_user_text)

        sync_project_to_chroma(target_dir)
        chroma_context = get_retrieved_context(
            latest_user_text or "estructura del proyecto", target_dir=target_dir
        )
        file_snapshot = "\n".join(list_files_internal(base_path=target_dir, max_items=120))

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            target_dir=target_dir,
            file_snapshot=file_snapshot,
            chroma_context=chroma_context,
        )

        try:
            response = llm_holder["client"].invoke(
                [SystemMessage(content=system_prompt), *state["messages"]]
            )
        except Exception as exc:
            message = str(exc)
            if ("NOT_FOUND" in message or "is not found" in message) and llm_holder["model"] != fallback_model:
                llm_holder["model"] = fallback_model
                llm_holder["client"] = ChatGoogleGenerativeAI(
                    model=fallback_model,
                    temperature=0.2,
                ).bind_tools(TOOLS)
                response = llm_holder["client"].invoke(
                    [SystemMessage(content=system_prompt), *state["messages"]]
                )
            else:
                raise

        return {"messages": [response]}

    graph_builder = StateGraph(MessagesState)
    graph_builder.add_node("reason", reasoning_node)
    graph_builder.add_node("tools", ToolNode(TOOLS))

    graph_builder.add_edge(START, "reason")
    graph_builder.add_conditional_edges("reason", tools_condition, {"tools": "tools", END: END})
    graph_builder.add_edge("tools", "reason")

    return graph_builder.compile()
