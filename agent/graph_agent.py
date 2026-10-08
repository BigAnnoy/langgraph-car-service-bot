from collections.abc import Iterable
from langgraph.graph import StateGraph,START,END
from langgraph.graph.message import MessagesState
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Literal
from langchain_core.messages import RemoveMessage, SystemMessage,HumanMessage
from langchain_core.messages import AIMessageChunk
from pydantic import BaseModel,Field
from agent.subgraphs.report_subgraph import build_report_subgraph
from agent.subgraphs.chat_subgraph import build_chat_subgraph
import sqlite3
from model.factory import get_chat_model
from utils.prompt_loader import load_prompt
from utils.path_tool import get_abs_path
from utils.config_handler import memory_config
from utils.logger_handler import logger
from langgraph.types import Command
from utils.llm_tools import DEFAULT_RETRY_COUNT
import re
from langgraph.store.sqlite import SqliteStore
from langgraph.graph.message import REMOVE_ALL_MESSAGES

class OverAllState(MessagesState):
    pass

_REPORT_KEYWORDS = ( "报告" , "报表" , "report" )

class IntentAnalysisOutput(BaseModel):
     intent:Literal["chat","report"]=Field(description="用户意图")

class GraphAgent():
    def __init__(self):
        memory_db_path=get_abs_path(memory_config["memory_db"])
        self.checkpointer=SqliteSaver(sqlite3.connect(memory_db_path,check_same_thread=False))
        self.store=SqliteStore(sqlite3.connect(memory_db_path,check_same_thread=False,isolation_level=None))
        self.store.setup()
        self.model=get_chat_model()
        self.graph=self.init_graph()
        self.intention_model=self.model.with_structured_output(IntentAnalysisOutput).with_config({"tags" : [ "nostream" ]})
        self.summarize_model=self.model.with_config({"tags" : [ "nostream" ]})
    
    def summarize_node(self,state:OverAllState):
        summarization_trigger=memory_config["summarization_trigger"]
        summarization_keep=memory_config["summarization_keep"]
        history_messages=state["messages"]
        if len(history_messages)>summarization_trigger:
            cut = len (history_messages) - summarization_keep 
            while cut > 0 and not isinstance (history_messages[cut], HumanMessage):
                cut -= 1 
            if cut <= 0 : 
                return None
            prompt=[SystemMessage(load_prompt("messages_summary"))]+history_messages[:cut]
            summarize=self.summarize_model.invoke(prompt)
            summarize=SystemMessage(content=summarize.content)
            messages=[summarize]+history_messages[cut:]
            logger.info(f'[summarize_node]历史消息压缩完成:{ len (history_messages)} -> { len (messages)} 条')
            return {"messages":[RemoveMessage(id=REMOVE_ALL_MESSAGES)]+messages}
        return None

        

    # 意图识别，根据用户输入判断是报告意图，还是聊天（通用）意图
    def intent_analysis(self,state:OverAllState)->Literal["chat","report"]:
        user_input= re.sub(r"[^\w\s]","",state["messages"][-1].content)
        if any(keyword in user_input for keyword in _REPORT_KEYWORDS):
            logger.info(f"意图识别：命中报告关键词，直接进入报告场景")
            return "report"
        raw=None
        for i in range(1,DEFAULT_RETRY_COUNT+1 ):
            try:
                logger.info(f"意图识别：开始调用大模型，重试次数：{i}/{DEFAULT_RETRY_COUNT}")
                raw=self.intention_model.invoke(
                [SystemMessage(content=load_prompt(type="intent_analysis"))]+state["messages"][-1:])
                break
            except Exception as e:
                logger.warning(f"意图识别第{i}次失败：{e}")
                continue
        if raw is None:
            logger.info(f"意图识别：大模型识别失败：返回兜底意图chat")
            return "chat"
        if "report" == raw.intent:
            logger.info(f"意图识别：大模型识别为报告意图，进入报告场景")
            return raw.intent
        elif "chat" == raw.intent:
            logger.info(f"意图识别：大模型识别为聊天意图，进入聊天场景")
            return raw.intent
        else:
            logger.info(f"意图识别：大模型识别失败：返回兜底意图chat")
            return "chat"

        # 如果重试次数超过最大重试次数，返回默认意图chat
    
    # 初始化父图 
    def init_graph(self)->StateGraph:
        builder = StateGraph[OverAllState, None, OverAllState, OverAllState](OverAllState)
        builder.add_node("summarize_node",self.summarize_node)
        builder.add_node("chat_scene_subgraph",build_chat_subgraph().compile())
        builder.add_node("report_scene_subgraph",build_report_subgraph().compile())
        # add edges
        builder.add_edge(START,"summarize_node")
        builder.add_conditional_edges("summarize_node",self.intent_analysis,{"chat":"chat_scene_subgraph","report":"report_scene_subgraph"})
        builder.add_edge("report_scene_subgraph",END)
        builder.add_edge("chat_scene_subgraph",END)
        graph=builder.compile(checkpointer=self.checkpointer,store=self.store)
        return graph
    
    # 开始流式输出
    def execute_stream(self,user_id:str,thread_id:str,query:str,callbacks=None)->Iterable[dict]:
        input={"messages":[HumanMessage(content=query)]}
        config={"configurable":{"thread_id":thread_id,"user_id":user_id},"callbacks":callbacks or []}
        logger.info( f"[execute_stream]收到用户输入： {query} " )
        return self._emit(self.graph.stream(input,stream_mode=["messages","updates","custom"],config=config,subgraphs=True,version="v2"))
    
    # 从中断中恢复流式输出
    def resume_stream(self,resume_decision:dict,user_id:str,thread_id:str,callbacks=None)->Iterable[dict]:
        logger.info(f"从中断中恢复流式输出，恢复决策：{resume_decision}")
        config={"configurable":{"thread_id":thread_id,"user_id":user_id},"callbacks":callbacks or []}
        return self._emit(self.graph.stream(Command(resume=resume_decision),stream_mode=["messages","updates","custom"],config=config,subgraphs=True,version="v2"))
    
    # 处理流式输出，提取有效内容，包含中断和AIMessage
    def _emit(self,raw_stream):
        for part in raw_stream:
            if part["type"]=="custom":
                data=part["data"]
                if data["type"]=="process":
                    yield {"process":data["content"]}
                elif data["type"]=="message" and "content" in data:
                    yield {"content":data["content"]}
            elif part["type"]=="messages":
                message_chunk,meta=part["data"]
                if isinstance(message_chunk,AIMessageChunk) and message_chunk.content:
                    yield {"content":message_chunk.content}
            elif part["type"]=="updates":
                data= part["data"]
                if "__interrupt__" in data:
                    yield {"interrupt":data["__interrupt__"][0].value}
                    return
        
if __name__ == "__main__":
    config={"configurable":{"thread_id":"123","user_id":"1001"}}
    graph_agent=GraphAgent()
    # result=graph_agent.invoke(
    #     input={"messages":[{"role":"user","content":"帮我生成一份2025年1月的机器使用报告"}]},
    #     config=config)
    result=graph_agent.execute_stream(
        query="帮我生成一份2025年1月的机器使用报告",
        user_id="1001",
        thread_id="123")
    print ("-"*50+"中断信息"+"-"*50)
    # print (result[ "__interrupt__" ][ 0 ].value)
    # result=graph_agent.invoke(Command(resume={"user_decision":"accept"}), config=config)
    # print ("-"*50+"最终回复"+"-"*50)
    # print(result["messages"][-1].content)
    