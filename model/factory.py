from langchain.embeddings.base import init_embeddings
from langchain.chat_models import init_chat_model
import dotenv
dotenv.load_dotenv()
from abc import ABC, abstractmethod
from langchain.chat_models.base import BaseChatModel
from langchain_core.embeddings import Embeddings
from typing import Optional
from utils.logger_handler import logger
from utils.config_handler import rag_config
import os

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass
    
class OllamaEmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Embeddings:
        """
        生成嵌入模型
        :return: 嵌入模型
        """
        return init_embeddings(rag_config["embedding_model_name"],base_url=os.getenv("ollama_base_url"))

class OllamaChatModelFactory(BaseModelFactory):
    def generator(self) -> BaseChatModel:
        """
        生成聊天模型
        :return: 聊天模型
        """
        return init_chat_model(rag_config["chat_model_name"],base_url=os.getenv("ollama_base_url"),api_key=os.getenv("ollama_api_key"),num_ctx=16384)

class DeepseekChatModelFactory(BaseModelFactory):
    def generator(self) -> BaseChatModel:
        """
        生成聊天模型
        :return: 聊天模型
        """
        return init_chat_model(rag_config["chat_model_name"],
                                base_url=os.getenv("deepseek_base_url"),
                                api_key=os.getenv("deepseek_api_key"), 
                                extra_body={"thinking": {"type": "disabled"}})
 
# 模型工厂注册表
_CHAT_MODEL_REGISTRY={
    "ollama":OllamaChatModelFactory,
    "deepseek":DeepseekChatModelFactory,
}
# 嵌入模型工厂注册表
_EMBEDDING_MODEL_REGISTRY={
    "ollama":OllamaEmbeddingsFactory,
}

_CHAT_MODEL_CACHE={}
_EMBEDDING_MODEL_CACHE={}

# 获取聊天模型
def get_chat_model():
    model_provider=rag_config["chat_model_name"].split(":")[0].lower()
    if model_provider not in _CHAT_MODEL_REGISTRY:
        raise ValueError(f"[RAG]不支持的聊天模型提供者{model_provider}")
    if model_provider not in _CHAT_MODEL_CACHE:
        _CHAT_MODEL_CACHE[model_provider]=_CHAT_MODEL_REGISTRY[model_provider]().generator()
        logger.info(f"[RAG]开始连接大语言模型{rag_config['chat_model_name']}")
    return _CHAT_MODEL_CACHE[model_provider]

# 获取嵌入模型
def get_embedding_model():
    model_provider=rag_config["embedding_model_name"].split(":")[0].lower()
    if model_provider not in _EMBEDDING_MODEL_REGISTRY:
        raise ValueError(f"[RAG]不支持的嵌入模型提供者{model_provider}")
    if model_provider not in _EMBEDDING_MODEL_CACHE:
        _EMBEDDING_MODEL_CACHE[model_provider]=_EMBEDDING_MODEL_REGISTRY[model_provider]().generator()
        logger.info(f"[RAG]开始连接嵌入模型{rag_config['embedding_model_name']}")
    return _EMBEDDING_MODEL_CACHE[model_provider]

# chat_model=get_chat_model()
# embedding_model=get_embedding_model()


