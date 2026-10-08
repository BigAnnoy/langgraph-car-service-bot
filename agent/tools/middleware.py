from langchain.agents.middleware import before_model,wrap_tool_call
from langchain.tools.tool_node import ToolCallRequest
from typing import Callable
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from utils.logger_handler import logger
from langgraph.runtime import Runtime
from langchain.agents import AgentState
from langchain.agents.middleware import dynamic_prompt,ModelRequest
from utils.prompt_loader import load_prompt

@wrap_tool_call
def monitor_tool(request:ToolCallRequest,handler:Callable[[ToolCallRequest],ToolMessage|Command])->ToolMessage|Command:
    """
    监控工具
    :return: 监控结果
    """
    logger.info(f"[monitor_tool]工具调用请求: {request.tool_call['name']}，请求参数: {request.tool_call['args']}")
    try:
        result=handler(request)
        logger.info(f"[monitor_tool]工具调用成功: {request.tool_call['name']}，响应参数: {result.content}")
        # 检查是否为fill_context_for_report工具
        if request.tool_call['name']=="fill_context_for_report":
            request.runtime.context["report"]=True
        return result
    except Exception as e:
        logger.error(f"[monitor_tool]工具 {request.tool_call['name']}调用异常,异常信息: {str(e)}")
        raise e

@before_model
def log_before_model(state:AgentState,runtime:Runtime):
    """
    模型调前日志
    :return: None
    """
    logger.info(f"[log_before_model]即将调用模型，携带: {len(state['messages'])}消息条历史消息")
    logger.debug(f"[log_before_model]即将调用模型，最新消息类型: {type(state['messages'][-1]).__name__}，内容: {state['messages'][-1].content.strip()}")
    return None

@dynamic_prompt
def report_prompt_switch(request:ModelRequest):
    """
    上报提示开关
    :return: 上报结果
    """
    is_report=request.runtime.context.get("report",False)
    if is_report:
        return load_prompt(type="report")
    return load_prompt(type="system")
