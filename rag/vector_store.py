"""
用于将知识文件加入RAG知识库
"""
from utils.logger_handler import logger
from utils.path_tool import get_abs_path
from utils.config_handler import milvus_config
import dotenv
from model.factory import get_embedding_model
dotenv.load_dotenv()
from langchain_text_splitters import RecursiveCharacterTextSplitter
import datetime
from langchain_milvus import Milvus
import sqlite3
from utils.file_handler import get_file_md5_hex, pdf_loader, txt_loader, listdir_with_allowed_type
import os
from langchain_core.documents import Document

class VectorStoreService:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=milvus_config["chunk_size"], chunk_overlap=milvus_config["chunk_overlap"], separators=milvus_config["separators"])
        self.embedding_model=get_embedding_model()
        self.vector_store = Milvus(
            embedding_function=self.embedding_model,
            connection_args={"uri":milvus_config["database_dir"]},
            collection_name=milvus_config["collection_name"],
            auto_id=True,
            primary_field="id",
            vector_field="vector",
            text_field="text",
            index_params={"index_type": "AUTOINDEX", "metric_type": "COSINE"})

    # 存储文本到向量数据库：将文本分块，对每个块进行嵌入，存储到向量数据库中
    def store_text(self, path: str, operator: str):
        """
        存储文本到向量数据库
        :param path: 文件路径
        :param operator: 操作人
        :return: None
        """
        
        # 计算文件的md5值
        file_name=os.path.basename(path)
        md5_hex=get_file_md5_hex(path)
        
        # 检查md5值是否存在
        logger.info(f"[RAG]开始检查md5值，文件名: {file_name}")
        md5_hex_store=Md5HexStore()
        if md5_hex is None:
            logger.error(f"[RAG]文件md5值计算失败，文件名: {file_name}")
            return {"result":"error","message":"文件md5值计算失败"}
        if md5_hex_store.check(md5_hex):
            logger.info(f"[RAG]文件已存在，跳过存储，文件名: {file_name}")
            return {"result":"error","message":"文件已存在，请勿重复存储"}
        # 文件不存在，开始存储流程
        logger.info(f"[RAG]文件不存在，开始存储文本块到向量数据库，文件名: {file_name}")

        # 加载文档
        documents:list[Document]=[]
        try:
            if path.endswith(".pdf"):
                documents=pdf_loader(path)
            elif path.endswith(".txt"):
                documents=txt_loader(path)
            else:
                logger.error(f"[RAG]文件类型错误: {file_name}")
                return {f"result":"error","message":f"不支持的文件类型: {path}"}
        except Exception as e:
            logger.error(f"[RAG]加载文档失败: {file_name}，{str(e)}",exc_info=True)
            return {f"result":"error","message":f"加载文档失败,{str(e)}"}
        # 检查文档是否为空
        if not documents:
            logger.error(f"[RAG]文件内容为空，文件名: {file_name}")
            return {f"result":"error","message":"文件内容为空，无法存储"}
        
        # 对文本进行分块
        chunks = self.text_splitter.split_documents(documents)
        logger.info(f"[RAG]文件名: {file_name},文本块分块完成，共分块{len(chunks)}个块")

        now=int(datetime.datetime.now().timestamp())
        for chunk in chunks:
            chunk.metadata["source"]=file_name
            chunk.metadata["operator"]=operator
            chunk.metadata["create_time"]=now
        self.vector_store.add_documents(chunks)
        logger.info(f"[RAG]文件名: {file_name},成功存储文本块到向量数据库，共存储{len(chunks)}条记录")
        # 存储md5值到数据库
        md5_hex_store.insert(md5_hex)
        logger.info(f"[RAG]文件名: {file_name},成功存储md5值到数据库")
        return {"result":"success","message":"文件已成功存储到向量数据库"}
        

    def get_retriever(self):
        """
        获取检索器
        :param k: 检索数量
        :return: 检索器
        """
        return self.vector_store.as_retriever(search_kwargs={"k":milvus_config["k"]})

    def load_documents(self) -> list:
        """
        加载文档
        :param source: 来源文件
        :return: 文档列表
        """
        files=listdir_with_allowed_type(get_abs_path(milvus_config["data_dir"]), tuple(milvus_config["allow_knowledge_types"]))
        for file in files:
            self.store_text(file, "system")

    

class Md5HexStore:
    """
    md5值存储类
    """
    def __init__(self):
        """
        初始化md5值存储类
        :return: None
        """ 
        self.sqlite_path=get_abs_path(milvus_config["md5_hex_store"])
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS md5_hex_store (md5_hex TEXT PRIMARY KEY,create_time INTEGER)")
            conn.commit()

    def check(self, md5_hex: str) -> bool:
        """
        检查md5_hex是否存在
        :param md5_hex: md5加密后的字符串
        :return: 是否存在
        """
        with sqlite3.connect(self.sqlite_path) as conn:
            row = conn.execute(f"SELECT * FROM md5_hex_store WHERE md5_hex=?", (md5_hex,)).fetchone()
        return row is not None

    def insert(self, md5_hex: str):
        """
        插入md5_hex到数据库
        :param md5_hex: md5加密后的字符串
        :return: None
        """
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(f"INSERT INTO md5_hex_store VALUES (?,?)", (md5_hex,int(datetime.datetime.now().timestamp())))
            conn.commit()
        return "success"

if __name__ == "__main__":
    vector_store_service = VectorStoreService()
    vector_store_service.load_documents()
    retriever=vector_store_service.get_retriever()
    results=retriever.invoke("特斯拉保养诀窍是什么")
    print(results)
    print("success")


