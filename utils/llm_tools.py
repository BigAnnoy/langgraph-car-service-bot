from langgraph.config import get_stream_writer
from utils.logger_handler import logger

# 负责自定义流式输出提示字符串
_DEFAULT_CHUNK_SIZE = 8
def stream_notice(content:str,chunk_size:int=_DEFAULT_CHUNK_SIZE,type:str="process")->None:
    """
    流式输出提示字符串
    :param content: 提示字符串
    :param chunk_size: 每个块的大小，默认8
    :param type: 输出类型，默认process,可选值为process,message。process代表过程状态，message代表消息。
    :return: None
    """
    writer=get_stream_writer()
    # process非流式
    if type=="process":
        writer({"content":content,"type":type})
    # message流式
    elif type=="message" and chunk_size>0:
        for i in range(0,len(content),chunk_size):
            writer({"content":content[i:i+chunk_size],"type":type})
    else:
        logger.info(f"[stream_notice]chunk_size为必须大于0，当前值为{chunk_size},直接一次性输出")
        writer({"content":content,"type":type})

DEFAULT_RETRY_COUNT = 3
