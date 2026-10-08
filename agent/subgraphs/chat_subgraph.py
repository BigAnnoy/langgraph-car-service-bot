from langgraph.graph import StateGraph,END,START
from langgraph.graph.message import MessagesState
from typing import Literal
from model.factory import get_chat_model
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage
from utils.prompt_loader import load_prompt
from agent.tools.agent_tools import rag_search,get_current_month,get_weather,get_user_location,get_long_term_memory,save_long_term_memory,get_user_artifacts_overview,get_user_artifact_detail
from langgraph.prebuilt import ToolNode
from utils.logger_handler import logger
from utils.hooks import default_tool_call_wrapper,trim_history_messages
from langgraph.types import RetryPolicy
from utils.llm_tools import stream_notice,DEFAULT_RETRY_COUNT

chat_tools=[rag_search,get_current_month,get_weather,get_user_location,get_long_term_memory,save_long_term_memory,get_user_artifacts_overview,get_user_artifact_detail]
model=get_chat_model()


class ChatState(MessagesState):
    """
    聊天状态类
    """

def chat_scene_node(state:ChatState)->ChatState:
    """
    聊天智能节点
    """
    model_with_tools=model.bind_tools(chat_tools)
    messages=[SystemMessage(content=load_prompt(type="system"))]+trim_history_messages(state[ "messages" ])
    logger.info(f"聊天智能节点：开始调用大模型")
    response= None 
    for i in range ( 1 ,DEFAULT_RETRY_COUNT+ 1 ):
        response=model_with_tools.invoke(messages) 
        if response.content or response.tool_calls: 
            break
        logger.warning( f"聊天智能节点：模型返回空响应，重试次数： {i} / {DEFAULT_RETRY_COUNT} " )
    if not response.content and not response.tool_calls:
        logger.error( f"聊天智能节点：重试 {DEFAULT_RETRY_COUNT} 次仍为空响应" )
        response=AIMessage(content= "抱歉，我这边刚才没能生成回复，请再说一次。" )
        stream_notice(content = "抱歉，我这边刚才没能生成回复，请再说一次。",type="message")
    logger.info(f"聊天智能节点：大模型回复：{response.content[:50]}...")
    return {"messages":[response]}

def tool_call_router(state:ChatState)->str:
    if state["messages"][-1].tool_calls:
        return "tool_call_node"
    else:
        return END


def build_chat_subgraph()->StateGraph:
    builder=StateGraph(ChatState)
    builder.add_node("chat_scene_node",chat_scene_node,retry_policy=RetryPolicy(max_attempts=3))
    builder.add_node("tool_call_node",
                    ToolNode(tools=chat_tools,
                            wrap_tool_call=default_tool_call_wrapper))
    builder.add_edge(START,"chat_scene_node")
    builder.add_conditional_edges("chat_scene_node",tool_call_router,{"tool_call_node":"tool_call_node",END:END})
    builder.add_edge("tool_call_node","chat_scene_node")
    
    return builder

if __name__=="__main__":
    graph=build_chat_subgraph().compile()
    result=graph.invoke({"messages":[HumanMessage(content="你好")]})

    print(result["messages"])
