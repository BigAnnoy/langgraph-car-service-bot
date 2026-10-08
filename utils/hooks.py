from langchain_core.messages import BaseMessage
from utils.logger_handler import logger
from langgraph.prebuilt.tool_node import ToolCallRequest
from typing import Callable
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langchain_core.messages import trim_messages

# 工具调用日志记录
def log_tool_call(request:ToolCallRequest,execute:Callable)->ToolMessage|Command:
    """
    包裹工具调用，添加上下文信息
    """
    tool_name = request.tool_call["name"]
    logger.info(f"调用工具中: {tool_name}")
    return execute(request)

# 工具调用重试
def retry_tool_call(request:ToolCallRequest,execute:Callable)->ToolMessage|Command:
    """
    包裹工具调用，添加重试机制
    """
    for i in range(3):
        try:
            result = execute(request)
            return result
        except Exception as e:
            logger.error(f"工具调用失败: {e},重试中: {i}")
            continue
    result = ToolMessage(content="工具调用失败，已经重试3次，建议手动检查",tool_call_id=request.tool_call["id"])
    logger.error(f"工具调用失败: {request.tool_call['name']},重试3次后仍失败")
    return result

# 工具调用hook包装组合
def combine_tool_call_hooks(wrappers:list[Callable])->Callable:
    """
    多个函数调用包装组合，用于包裹工具调用
    要求：
    1. 所有包装函数的参数必须是ToolCallRequest和Callable
    2. execute参数必须是单个参数的Callable，参数类型为ToolCallRequest，返回值类型为ToolMessage或Command
    3. 所有包装函数的返回值必须是ToolMessage或Command
    """
    def composed(request:ToolCallRequest,execute:Callable):
        seed = execute
        for wrapper in wrappers:
            seed = lambda request,w=wrapper,inner=seed: w(request,inner)
        return seed(request)
    return composed

# 通用工具调用包装,建议直接使用
default_tool_call_wrapper:Callable=combine_tool_call_hooks([retry_tool_call,log_tool_call])

# 消息截断
def trim_history_messages(messages:list[BaseMessage],max_tokens:int=3000)->list[BaseMessage]:
    """
    截断消息列表，确保总token数不超过指定值
    """
    return trim_messages(messages,max_tokens=max_tokens,token_counter="approximate",strategy="last",start_on="human",end_on=("human","tool"),include_system=True)
