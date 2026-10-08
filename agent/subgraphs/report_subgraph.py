from langgraph.graph import StateGraph,END,START
from langgraph.graph.message import MessagesState,add_messages
from typing import Literal
from model.factory import get_chat_model
from langchain_core.messages import SystemMessage,AIMessage,HumanMessage
from services.long_term_memory_service import append_memory
from utils.prompt_loader import load_prompt
from agent.tools.agent_tools import fetch_external_data
from langgraph.prebuilt import ToolNode
from langgraph.types import Command,interrupt
from utils.logger_handler import logger
from utils.llm_tools import stream_notice,DEFAULT_RETRY_COUNT
from utils.hooks import default_tool_call_wrapper   
from agent.tools.agent_tools import get_user_artifacts_overview,get_user_artifact_detail,get_current_month,rag_search
from langgraph.types import RunnableConfig
from services.artifact_service import ArtifactService
from typing import Annotated
from langchain_core.messages import BaseMessage
from langgraph.types import RetryPolicy
from pydantic import BaseModel,Field
from langgraph.config import get_store
from services.long_term_memory_service import render_value
report_tools=[fetch_external_data,get_user_artifacts_overview,get_user_artifact_detail,get_current_month,rag_search]
model=get_chat_model()
# 报告状态
class ReportState(MessagesState):
    user_decision:Literal["accept","cancel","edit"]
    user_edit_content:str
    draft_report:str
    final_report:str
    quality_score:int
    subgraph_messages:Annotated[list[BaseMessage],add_messages]
    regenerate_count:int

# 消息转换节点
def messages_transform_node(state:ReportState,config:RunnableConfig=None)->ReportState:
    ns=('long_term_memory',config["configurable"]["user_id"],"偏好")
    item = get_store().get(ns,'报告要求')
    items=item.value.get("value") if item else None
    prompt= [SystemMessage(content=load_prompt(type="report"))]+[state["messages"][-1]]
    history_preference=render_value(items)
    if history_preference:
        prompt+= [SystemMessage(content=f"用户历史报告偏好，请在本次生成中严格遵守（如历史要求之间有冲突，以最新的为准）:\n{history_preference}")]
    return {"subgraph_messages":prompt,"regenerate_count":0}


# 报告智能体节点
def report_scene_node(state:ReportState)->ReportState:
    model_with_tools=model.bind_tools(report_tools).with_config({"tags" : [ "nostream" ]})
    stream_notice("开始生成报告",type="process")
    response=model_with_tools.invoke(state["subgraph_messages"])
    return {"subgraph_messages":[response],"draft_report":response.content}

# 工具调用路由
def tool_call_router(state:ReportState)->Literal["tool_call","quality_agent_node"]:
    if state["subgraph_messages"][-1].tool_calls:
        return "tool_call"
    else:
        return "quality_agent_node"



# 质量智能体
class QualityScore ( BaseModel ):
    score: int = Field(description="报告质量分数",ge=0,le=100)
quality_model=model.with_structured_output(QualityScore).with_config({"tags" : [ "nostream" ]})
def quality_agent_node(state:ReportState)->Command:
    logger.info(f"[quality_agent_node]报告生成完成，开始AI质检,报告内容：\n{state['draft_report'].strip()[:50]}...")
    stream_notice("报告生成完成，开始AI质检",type="process")
    # 质检分数解析重试
    quality_score=None
    for i in range(1,DEFAULT_RETRY_COUNT+1 ):
        try:
            quality_score=quality_model.invoke([SystemMessage(content=load_prompt(type="report_quality"))]+[state["draft_report"]]).score
            break
        except Exception as e: 
            logger.warning(f"[quality_agent_node]质检调用第{i}次失败：{e}")
            continue
        # m= re.search( r"(\d{1,3})" , raw)
        # if m:
        #     quality_score=int(m.group(1))
        #     break
    # 质检分数解析失败
    if quality_score is None:
        logger.error(f"[quality_agent_node]质检分数解析失败，重试{DEFAULT_RETRY_COUNT}次")
        stream_notice(f"质检分数解析失败，请人工检查报告内容是否符合要求。",type="process")
        return Command(goto="user_decision_node",update={"quality_score":-1,"regenerate_count":0})
    # 质检分数解析成功
    # 质检分数低于80分，建议重新生成报告，最多重试DEFAULT_RETRY_COUNT次
    elif quality_score  < 80:
        count= state["regenerate_count"]+1
        if count>DEFAULT_RETRY_COUNT:
            logger.info(f"[quality_agent_node]连续{DEFAULT_RETRY_COUNT}次质检失败，建议人工检查报告内容是否符合要求。")
            stream_notice(f"连续{DEFAULT_RETRY_COUNT}次质检失败，建议人工检查报告内容是否符合要求。",type="process")
            return Command(goto="user_decision_node",update={"quality_score":-1,"regenerate_count":count})
        
        logger.info(f"[quality_agent_node]报告质量分数为{quality_score}，建议重新生成报告")
        stream_notice(f"报告质量分数为{quality_score}，重新生成报告中...",type="process")
        return Command(goto="report_scene_node",
                            update={"subgraph_messages":[AIMessage(content=f"质检Agent自动审阅，报告质量分数为{quality_score}，请重新生成报告。")],
                            "quality_score":quality_score,"regenerate_count":count})
    # 质检分数高于等于80分，建议接受报告
    else:
        logger.info(f"[quality_agent_node]报告质量分数为{quality_score}，建议接受报告")
        stream_notice(f"报告质量分数为{quality_score}，建议接受报告。",type="process")
        return Command(goto="user_decision_node",update={"quality_score":quality_score,"regenerate_count":0})
    
# 用户决策
def user_decision_node(state:ReportState,config:RunnableConfig=None)->Command:
    if state["quality_score"] == -1:
        decision=interrupt(f"已完成报告生成，AI质检失败，请人工审阅报告，决定是否修改并重新生成、或取消生成报告，报告内容：\n{state['draft_report']}")
    else:
        decision=interrupt(f"已完成报告生成，AI质检分数为{state['quality_score']}，请审阅报告，决定是否修改并重新生成、或取消生成报告，报告内容：\n{state['draft_report']}")
    if decision["user_decision"]=="accept":
        # 保存报告
        store_result=ArtifactService().save_artifact(config["configurable"]["user_id"],"report",content=state["draft_report"])
        artifact_id=store_result["artifact_id"]
        logger.info(f"[user_decision_node]定稿报告已保存。")
        decision_info=f"用户接受报告。"
        logger.info(f"[user_decision_node]{decision_info}")
        stream_notice(decision_info+"\n"+"报告内容：\n"+state["draft_report"],type="message")
        return Command(goto=END,update={"final_report":state["draft_report"],"messages":[AIMessage(content=decision_info+f"报告已保存至数据库(ID={artifact_id})。可用工具get_user_artifact_detail 查看详情")]})
    elif decision["user_decision"]=="cancel":
        decision_info=f"用户取消本次报告生成。"
        logger.info(f"[user_decision_node]{decision_info}")
        stream_notice(decision_info,type="message")
        return Command(goto=END,update={"messages":[AIMessage(content=decision_info)]})
    elif decision["user_decision"]=="edit":
        if decision['user_edit_content']:
            try:
                append_memory(get_store(),config["configurable"]["user_id"],category="偏好",attr="报告要求",value=decision['user_edit_content'])
                logger.info( f"[user_decision_node]用户偏好：报告要求，写入成功" )
            except Exception as e:
                logger.warning( f"[user_decision_node]用户偏好：报告要求，写入失败： {e} " )
        decision_info=f"用户期望重新生成报告，用户建议: {decision['user_edit_content']}。"
        logger.info(f"[user_decision_node]{decision_info}")
        stream_notice(decision_info,type="message")
        return Command(goto="report_scene_node",update={"subgraph_messages":[HumanMessage(content=decision_info)]})
    else:
        decision_info="接收用户选择异常"
        logger.info(f"[user_decision_node]{decision_info}")
        stream_notice(decision_info,type="message")
        return Command(goto=END,update={"messages":[AIMessage(content=decision_info)]})
    
# 报告智能体子图
def build_report_subgraph()->StateGraph:
    builder=StateGraph(ReportState)
    # 节点
    builder.add_node("messages_transform_node",messages_transform_node)
    builder.add_node("tool_call",ToolNode(tools=report_tools,wrap_tool_call=default_tool_call_wrapper,messages_key="subgraph_messages"))
    builder.add_node("quality_agent_node",quality_agent_node,retry_policy=RetryPolicy(max_attempts=3))
    builder.add_node("user_decision_node",user_decision_node)
    builder.add_node("report_scene_node",report_scene_node,retry_policy=RetryPolicy(max_attempts=3))
    # 边
    builder.add_edge(START,"messages_transform_node")
    builder.add_edge("messages_transform_node","report_scene_node")
    builder.add_conditional_edges("report_scene_node",tool_call_router,{"tool_call":"tool_call","quality_agent_node":"quality_agent_node"})
    builder.add_edge("tool_call","report_scene_node")
    return builder

if __name__ == "__main__":
    report_agent_subgraph=build_report_subgraph().compile()
    config={"configurable":{"thread_id":"123","user_id":"1001"}}
    result=report_agent_subgraph.invoke({"messages":[HumanMessage(content="帮我生成一份2025年1月的机器使用报告")]},config=config)
    print ("-"*50+"中断信息"+"-"*50)
    print (result[ "__interrupt__" ][ 0 ].value)
    result=report_agent_subgraph.invoke(Command(resume={"user_decision":"accept"}), config=config)
    print ("-"*50+"最终报告"+"-"*50)
    print (result["final_report"])
