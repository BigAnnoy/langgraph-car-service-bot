import yaml
from utils.path_tool import get_abs_path

def load_rag_config(config_path:str=get_abs_path("config/rag.yaml"),encoding:str="utf-8") :
    """
    加载rag配置文件
    :return: rag配置字典
    """
    with open(config_path, "r", encoding=encoding) as f:
        config = yaml.load(f,Loader=yaml.FullLoader)
    return config

def load_milvus_config(config_path:str=get_abs_path("config/milvus.yaml"),encoding:str="utf-8") :
    """
    加载milvus配置文件
    :return: milvus配置字典
    """
    with open(config_path, "r", encoding=encoding) as f:
        config = yaml.load(f,Loader=yaml.FullLoader)
    return config


def load_prompt_config(config_path:str=get_abs_path("config/prompt.yaml"),encoding:str="utf-8") :
    """
    加载prompt配置文件
    :return: prompt配置字典
    """
    with open(config_path, "r", encoding=encoding) as f:
        config = yaml.load(f,Loader=yaml.FullLoader)
    return config

def load_agent_config(config_path:str=get_abs_path("config/agent.yaml"),encoding:str="utf-8") :
    """
    加载agent配置文件
    :return: agent配置字典
    """
    with open(config_path, "r", encoding=encoding) as f:
        config = yaml.load(f,Loader=yaml.FullLoader)
    return config

def load_memory_config(config_path:str=get_abs_path("config/memory.yaml"),encoding:str="utf-8") :
    """
    加载memory配置文件
    :return: memory配置字典
    """
    with open(config_path, "r", encoding=encoding) as f:
        config = yaml.load(f,Loader=yaml.FullLoader)
    return config

def load_business_config(config_path:str=get_abs_path("config/business.yaml"),encoding:str="utf-8") :
    """
    加载business配置文件
    :return: business配置字典
    """
    with open(config_path, "r", encoding=encoding) as f:
        config = yaml.load(f,Loader=yaml.FullLoader)
    return config


business_config = load_business_config()
memory_config = load_memory_config()
rag_config = load_rag_config()
milvus_config = load_milvus_config()
prompts_config = load_prompt_config()
agent_config = load_agent_config()

if __name__ == "__main__":
    print(rag_config)
    