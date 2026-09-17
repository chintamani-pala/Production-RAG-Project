"""
This file demonstates how to use LangChain & Langgraph for production-grade Agent development.
"""

from typing import Optional
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langsmith import traceable
from app.config import get_settings 
import litellm
from langchain_litellm import ChatLiteLLM, LiteLLMEmbeddings
from app.monitoring import get_logger
import litellm

litellm._turn_on_debug()

logger = get_logger()

class AgentState(TypedDict):
    """
    State for the production agent
    Uses Annotated with add_messages reducer for message accumulation.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    error: Optional[str]
    retry_count: int
    model_used: str


class ProductionAgent:
    """
    Production Langgraph agent with:
    - Retry on failure(model fallback)
    - Graceful error handling
    - Langsmith tracing
    """
    def __init__(self):
        settings = get_settings()

        self.primary_llm = ChatLiteLLM(
            model_name=settings.LITELLM_PRIMARY_CHAT_MODEL,
            temperature=0,
            request_timeout=30,
            max_retries=0, # We handle retries outselves
            api_key=settings.LITELLM_CHAT_API_KEY
        )

        self.fallback_llm = ChatLiteLLM(
            model_name=settings.LITELLM_FALLBACK_CHAT_MODEL,
            temperature=0,
            request_timeout=30,
            max_retries=0, # We handle retries outselves
            api_key=settings.LITELLM_CHAT_API_KEY
        )

        self.max_retries = settings.MAX_RETRIES
        self.graph=self._build_graph()

    @staticmethod
    def clean_response_content(content) -> str:
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []

            for item in content:
                if isinstance(item, str):
                    parts.append(item)

                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        text = item.get("text")
                        if isinstance(text, str):
                            parts.append(text)

            return "".join(parts)

        return str(content)


    def _build_graph(self):
        """
        Build the langgraph state machine
        """

        def process_message(state: AgentState) -> dict:
            """
            Try to process the message with the primary model.
            """
            try:
                response = self.primary_llm.invoke(state['messages'])
                response.content = self.clean_response_content(response.content)
                return {
                    "messages":[response],
                    "error": None,
                    "model_used":"primary"
                }
            except Exception as e:
                logger.exception("Primary LLM processing failed")
                return {
                    "error":str(e),
                    "model_used":"",
                    "retry_count":state['retry_count']+1
                }
        def try_fallback(state: AgentState)->dict:
            """
            Try to process with fallback LLM if within retry budget
            """
            
            try:
                response = self.fallback_llm.invoke(state['messages'])
                response.content = self.clean_response_content(response.content)
                return {
                    "messages":[response],
                    "error":None,
                    "model_used":"fallback"
                }
            except Exception as e:
                logger.exception("Fallback LLM processing failed")
                return {
                    "error":str(e),
                    "model_used":"",
                    "retry_count":state['retry_count']+1
                }
        
        def handle_error(state: AgentState) -> dict:
            """
            Return a graceful error message.
            """
            return {
                "messages":[
                    AIMessage(content=(
                        "I'm sorry, I'm having trouble processing your request "
                        "right now. Please try again in a moment"
                    ))
                ],
                "model_used":"error_handler"
            }
        
        def route_after_process(state: AgentState) -> str:
            """
            Decide what to do after primary model attempt
            """
            if state.get("error") is None:
                return "done"
            elif state["retry_count"] < self.max_retries:
                return "fallback"
            else:
                return "error"
        
        def route_after_fallback(state: AgentState) -> str:
            """
            Decide what to do after fallback attemot.
            """
            if state.get("error") is None:
                return "done"
            else:
                return "error"
        
        # Build the graph
        # pyrefly: ignore [bad-specialization]
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("process", process_message)
        graph.add_node("fallback", try_fallback)
        graph.add_node("error", handle_error)

        # Wire up the nodes
        graph.add_edge(START, "process")
        graph.add_conditional_edges(
            "process",
            route_after_process,
            {"done": END, "fallback":"fallback", "error":"error"}
        )
        graph.add_conditional_edges(
            "fallback",
            route_after_fallback,
            {"done": END, "error":"error"}
        )

        # Terminal nodes
        graph.add_edge("error", END)

        return graph.compile()
    
    @traceable(name="production_agent_invoke")
    def invoke(self, message: str) -> dict:
        """
        Invoke the agent with a user message.
        Returns: {"response": str, "model_used": str, "error": str | None}
        
        """
        result = self.graph.invoke({
            "messages":[HumanMessage(content=message)],
            "error": None,
            "retry_count": 0,
            "model_used": ""
        }) 

        return {
            "response": result['messages'][-1].content,
            "model_used":result.get('model_used', "unknown"),
            "error":result.get('error')
        }
