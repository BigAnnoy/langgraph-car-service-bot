from langchain_core.tools import tool
from rag.rag_service import RagService
from utils.path_tool import get_abs_path
from utils.config_handler import agent_config
from utils.logger_handler import logger
from pydantic import BaseModel,Field,model_validator
from utils.config_handler import memory_config
from typing import Literal
from services.artifact_service import ArtifactService
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from services.long_term_memory_service import append_memory,render_value
# RAG工具
_rag_service = None
def get_rag_service()->RagService|None:
    """
    获取RAG服务
    :return: RAG服务
    """
    global _rag_service
    if not _rag_service:
        _rag_service = RagService()
    return _rag_service

@tool(description="根据查询内容，搜索知识库的向量数据库，返回相关文档。输入：用户查询字符串，输出：相关文档的字符串。")
def rag_search(query: str) -> str:
    """
    对查询进行搜索
    :param query: 用户查询字符串
    :return: 相关文档的字符串
    """
    try:
        result = get_rag_service().rag_search(query)
        return result
    except Exception as e:
        logger.error(f"RAG搜索失败: {e}")
        return "RAG搜索失败，请稍后重试。"


@tool(description="获取当前月份，返回当前月份的字符串，str类型，格式为YYYY-MM，例如2024-08。")
def get_current_month()->str:
    """
    获取当前月份
    :return: 当前月份
    """
    return "2025-01"

@tool(description="根据定位信息，返回该位置的天气，str类型。")
def get_weather(location:str)->str:
    """
    获取当前的天气
    :param location: 定位信息
    :return: 当前的天气
    """
    return f"{location}的天气是晴，温度22摄氏度，湿度60%，风速10km/h，气压1013hPa。"

@tool(description="获取当前用户的定位信息，返回用户定位信息的字符串，str类型。用户定位信息是一个包含用户位置信息的字符串，例如北京市海淀区。")
def get_user_location()->str:
    """
    获取当前用户的定位信息
    :return: 当前用户的定位信息
    """
    return "北京市朝阳区"

external_data = {}
def load_external_data()->dict:
    """
    加载外部数据
    :return: 外部数据
    """
    # 从外部数据文件中读取数据
    if not external_data:
        with open(get_abs_path(agent_config["external_data_path"]), "r", encoding="utf-8") as file:
            data = file.readlines()
            for i in data:
                i=i.strip()
                i = i.split(",")
                user_id = i[0].strip().replace('"', "")
                features = i[1].strip().replace('"', "")
                clean_effect= i[2].strip().replace('"', "")
                consumables = i[3].strip().replace('"', "")
                comparison = i[4].strip().replace('"', "")
                month = i[5].strip().replace('"', "")
                if user_id not in external_data.keys():
                    external_data[user_id] = {}
                external_data[user_id][month] = {
                    "车辆档案": features,
                    "车辆健康": clean_effect,
                    "保养耗材": consumables,
                    "横向对比": comparison,
                }
    return external_data

@tool(description="根据查询月份，返回用户数据，dict类型。用户数据是一个包含车辆档案、车辆健康、保养耗材、横向对比的字典。")
def fetch_external_data(month:str,config:RunnableConfig)->dict:
    """
    获取用户数据
    :param month: 查询月份
    :return: 用户数据
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        return {"result":"error","message":"用户ID不存在"}
    load_external_data()
    try:
        return external_data[user_id][month]
    except KeyError:
        logger.warning(f"[fetch_user_data]用户在{month}月没有数据")
        return {"result":"error","message":"用户在该月份没有数据"}


# @tool(description="无入参返回值，调用后触发中间件自动为报告生成场景动态注入上下文信息，为后续提示词切换提供上下文信息。")
# def fill_context_for_report():
#     return "fill_context_for_report已调用"


# 保存长期长期记忆
_CATEGORIES_CONFIGS = memory_config["long_term_memory_categories"]
_CATEGORY_ATTRS={item["category"]:item["attrs"] for item in _CATEGORIES_CONFIGS}
_CATEGORY_ATTRS_LIST=[item for attrs in _CATEGORY_ATTRS.values() for item in attrs]
_CATEGORY_LIST=list(_CATEGORY_ATTRS.keys())
_APPEND_ATTRS= set (memory_config.get( "append_attrs" ,[]))
_APPEND_MAX_CHARS=memory_config.get( "append_max_chars" , 500 )

class LongTermMemoryData(BaseModel):
    category: Literal["用户画像","事实","偏好"] =Field(description="分类")
    attr: str =Field(description=(f"属性，必填,取值为从{_CATEGORY_ATTRS_LIST}中选择"))
    value: str =Field(description="属性对应的值，如北京市海淀区、男、25岁、高、低、高等。")

    @model_validator(mode="after")
    def _check_mapping(self):
        allowed = _CATEGORY_ATTRS.get(self.category, [])
        if self.attr not in allowed:
            raise ValueError(
                f"分类「{self.category}」的属性必须从 {allowed} 中选择，"
                f"不能使用「{self.attr}」"
            )
        return self

@tool(description="根据对话中可以提取到的用户画像、偏好和事实，分类后，保存长期记忆。",args_schema=LongTermMemoryData)
def save_long_term_memory(category:str,attr:str,value:str,config:RunnableConfig)->dict:
    """
    保存长期长期记忆
    :param category: 分类
    :param attr: 属性
    :param value: 值
    :return: 保存结果
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        return {"result":"error","message":"用户ID不存在"}
    store=get_store()
    if attr in _APPEND_ATTRS:
        append_memory(store,user_id,category,attr,value)
        logger.info(f"[save_long_term_memory]用户{user_id}已追加长期记忆{category}:{attr}={value}")
    else:
        store.put(namespace=('long_term_memory',user_id,category),key=attr,value={"value":value})
        logger.info(f"[save_long_term_memory]用户{user_id}保存长期记忆{category}:{attr}={value}")
    return {"result":"success","message":"保存成功"}


# 获取长期长期记忆内容
class LongTermMemoryGetData(BaseModel):
    category: Literal["用户画像","事实","偏好"]|None =Field(description="分类")
    attr: str|None =Field(description="属性，如用户地区、性别、年龄、车型、电池健康度、上次保养时间等")
@tool(description="根据长期记忆分类和属性，返回用户长期记忆内容，list[dict]类型。每个dict包含分类category、属性attr、值value、时间updated_at。",args_schema=LongTermMemoryGetData)
def get_long_term_memory(category:str=None,attr:str=None,config:RunnableConfig=None)->list[dict]:
    """
    获取长期长期记忆内容
    :param category: 分类
    :param attr: 属性
    :return: 长期长期记忆内容
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        return []
    store=get_store()
    items=store.search(('long_term_memory',user_id),limit=100)
    return [
        { "category" :i.namespace[- 1 ], "attr" :i.key, "value" :render_value(i.value.get( "value" )), "updated_at" : str (i.updated_at)} 
        for i in items 
        if (category is None or i.namespace[- 1 ]==category) 
        and (attr is None or i.key==attr)
    ]

# 获取用户产物概览
class ArtifactOverviewArgs(BaseModel):
    category: Literal["report"]=Field(description="产物类型")

@tool(description="根据产物类型，返回用户产物概览，list[dict]类型。每个dict包含产物ID artifact_id、分类category、标题title、创建时间create_time。",args_schema=ArtifactOverviewArgs)
def get_user_artifacts_overview(category:str,config:RunnableConfig=None)->list[dict]:
    """
    获取用户产物概览
    :param category: 产物类型
    :return: 用户产物概览
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        return []
    return ArtifactService().query_artifact_overview(user_id,category)

# 获取单个用户产物详情
class ArtifactDetailArgs(BaseModel):
    artifact_id: str =Field(description="产物ID")

@tool(description="根据产物ID，返回单个用户产物详情，dict类型。每个dict包含产物ID artifact_id、分类category、标题title、内容content、创建时间create_time。",args_schema=ArtifactDetailArgs)
def get_user_artifact_detail(artifact_id:str,config:RunnableConfig=None)->dict:
    """
    获取单个用户产物详情
    :param artifact_id: 产物ID
    :return: 用户产物详情
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        return {"result":"error","message":"用户ID不存在"}
    return ArtifactService().query_artifact_detail(user_id,artifact_id)
    