from rag.vector_store import VectorStoreService
from utils.logger_handler import logger
from langchain_core.documents import Document

class RagService:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
       
    def retriever_docs(self, query: str) -> list[Document]:
        """
        从向量数据库中检索与查询相关的文档
        :param query: 用户查询
        :return: 相关文档的列表
        """
        return self.retriever.invoke(query)

    def rag_search(self, query: str) -> str:
        """
        对查询进行搜索
        :param query: 用户查询
        :return: 搜索结果
        """
        docs = self.retriever_docs(query)
        if not docs:
            return "没有找到相关文档"
        logger.info(f"查询:{query}，找到{len(docs)}条相关文档")
        context=""
        for i,doc in enumerate(docs):
            context+=f"【参考资料{i+1}】:\n{doc.page_content}\n参考来源:{doc.metadata['source']}\n\n"    
        return context
   

if __name__ == "__main__":
    rag_service = RagService()
    query = "扫拖机器人如何保养"
    result = rag_service.rag_search(query)
    print(result)
    print("success")