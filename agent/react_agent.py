from langchain_core.messages import HumanMessage

from model.factory import get_chat_model
from utils.prompt_loader import load_system_prompt
from langchain.agents import create_agent
from agent.tools.agent_tools import rag_search,get_current_month,get_weather,get_user_location,fetch_external_data,fill_context_for_report,get_long_term_memory,save_long_term_memory
from agent.tools.middleware import report_prompt_switch,monitor_tool,log_before_model
from collections.abc import Iterable
from langchain_core.messages import AIMessageChunk
from langgraph.checkpoint.sqlite import SqliteSaver
from utils.path_tool import get_abs_path
from utils.config_handler import memory_config
import sqlite3
from langchain.agents.middleware import SummarizationMiddleware
class ReactAgent():
    def __init__(self):
        self._conn = sqlite3.connect(get_abs_path(memory_config["short_term_memory_save"]),check_same_thread=False)
        self.checkpointer=SqliteSaver(self._conn)
        self.model=get_chat_model()
        self.agent=create_agent(
            model=self.model,
            tools=[rag_search,get_current_month,get_weather,get_user_location,fetch_external_data,fill_context_for_report,get_long_term_memory,save_long_term_memory],
            system_prompt=load_system_prompt(),
            middleware=[report_prompt_switch,monitor_tool,log_before_model,
                SummarizationMiddleware(
                    model=self.model,
                    trigger=[("messages",memory_config["summarization_trigger"])],
                    keep=("messages",memory_config['summarization_keep'])
                    )],
            checkpointer=self.checkpointer
        )

    def execute_stream(self,user_id:str,thread_id:str,query:str)->Iterable[str]:
        input={"messages":[HumanMessage(content=query)]}
        for chunk in self.agent.stream(input,stream_mode="messages",context={"report":False},config={"configurable":{"thread_id":thread_id,"user_id":user_id}}):
            message_chunk,metadata=chunk
            if not isinstance(message_chunk,AIMessageChunk):
                continue
            if message_chunk.content:
                yield message_chunk.content

    def resume_stream(self,decision:dict,user_id:str,thread_id:str,query:str)->Iterable[str]:
        input={"messages":[HumanMessage(content=query)]}
        for chunk in self.agent.stream(input,stream_mode="messages",context={"report":False},config={"configurable":{"thread_id":thread_id,"user_id":user_id}}):
            message_chunk,metadata=chunk
            if not isinstance(message_chunk,AIMessageChunk):
                continue
            if message_chunk.content:
                yield {"type":"aimessage","content":message_chunk.content}
        yield {"type":"interrupt","content":chunk["__interrupt__"][0].value} if "__interrupt__" in chunk else None

if __name__ == "__main__":
    agent=ReactAgent()
    for chunk in agent.execute_stream(user_id="1",thread_id="1",query="扫地机器人在我所在地区的气温下如何保养"):
        print(chunk,flush=True,end="")
        