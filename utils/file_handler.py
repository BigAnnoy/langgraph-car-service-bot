import os
from utils.logger_handler import logger
import hashlib
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

def get_file_md5_hex(file_path: str) -> str:
    """
    获取文件的MD5哈希值（十六进制字符串）
    :param file_path: 文件路径
    :return: 文件的MD5哈希值（十六进制字符串）
    """
    if not os.path.exists(file_path):
        logger.error(f"[md5计算]文件不存在: {file_path}")
        return None

    if not os.path.isfile(file_path):
        logger.error(f"[md5计算]路径不是文件: {file_path}")
        return None

    md5_obj=hashlib.md5()
    chunk_size = 4096
    try:
        with open(file_path, "rb") as f:  # 必须以二进制读取文件
            # 以chunk_size为单位读取文件内容
            while chunk := f.read(chunk_size):
                    md5_obj.update(chunk)
            md5_hex=md5_obj.hexdigest()
            return md5_hex    
    except Exception as e:
        logger.error(f"[md5计算]计算文件MD5哈希失败: {file_path}，{str(e)}")
        return None

def listdir_with_allowed_type(dir_path: str, allowed_types: tuple[str]) -> tuple[str]:
    """
    列出目录下所有指定类型的文件
    :param dir_path: 目录路径
    :param allowed_types: 允许的文件类型元组（不包含点）
    :return: 目录下所有指定类型的文件路径元组
    """
    files=[]
    if not os.path.exists(dir_path):
        logger.error(f"[listdir_with_allowed_type]目录不存在: {dir_path}")
        return []
    if not os.path.isdir(dir_path):
        logger.error(f"[listdir_with_allowed_type]路径不是目录: {dir_path}")
        return []
    for f in os.listdir(dir_path):
        if f.endswith(allowed_types):
            files.append(os.path.join(dir_path, f))
    return tuple(files)
    
def pdf_loader(pdf_path: str,password:str=None,encoding:str="utf-8") -> list[Document]:
    """
    加载PDF文件
    :param pdf_path: PDF文件路径
    :param password: PDF文件密码，默认None
    :return: PDF文件内容（Document列表）
    """

    return PyPDFLoader(pdf_path,password=password,encoding=encoding).load()

def txt_loader(txt_path: str,encoding:str="utf-8") -> list[Document]:
    """
    加载TXT文件
    :param txt_path: TXT文件路径
    :return: TXT文件内容（Document列表）
    """
    return TextLoader(txt_path,encoding=encoding).load()
