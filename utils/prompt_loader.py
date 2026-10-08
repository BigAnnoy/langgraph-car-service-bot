from utils.config_handler import prompts_config
from utils.path_tool import get_abs_path
from utils.logger_handler import logger

# def load_system_prompt() -> str:
#     """
#     加载系统提示
#     :return: 系统提示（字符串）
#     """
#     try:
#         system_prompt_path=get_abs_path(prompts_config["main_prompt_path"])
#     except KeyError as e:
#         logger.error(f"[load_system_prompt]加载系统提示词失败: 在yaml配置文件中未找到main_prompt_path键")
#         raise e
#     try:
#         with open(system_prompt_path, "r", encoding="utf-8") as f:
#             system_prompt = f.read()
#     except Exception as e:
#         logger.error(f"[load_system_prompt]解析系统提示词失败: {system_prompt_path}，{str(e)}")
#         return None
#     return system_prompt

# def load_report_prompt() -> str:
#     """
#     加载report提示
#     :return: report提示（字符串）
#     """
#     try:
#         report_prompt_path=get_abs_path(prompts_config["report_prompt_path"])
#     except KeyError as e:
#         logger.error(f"[load_report_prompt]加载report提示词失败: 在yaml配置文件中未找到report_prompt_path键")
#         raise e
#     try:
#         with open(report_prompt_path, "r", encoding="utf-8") as f:
#             report_prompt = f.read()
#     except Exception as e:
#         logger.error(f"[load_report_prompt]解析report提示词失败: {report_prompt_path}，{str(e)}")
#         return None
#     return report_prompt

def load_prompt(type:str)->str:
    try:
        prompt_path_key=prompt_map[type]
    except KeyError as e:
        logger.error(f"[load_prompt]加载提示词失败: 不支持类型为{type}的提示词加载")
        raise e
    try:
        prompt_path=get_abs_path(prompts_config[prompt_path_key])
    except KeyError as e:
        logger.error(f"[load_prompt]加载提示词失败: 在yaml配置文件中未找到{prompt_path_key}键")
        raise e
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read()
    except Exception as e:
        logger.error(f"[load_prompt]解析提示词失败: {prompt_path}，{str(e)}")
        return None
    return prompt

prompt_map={"system":"main_prompt_path",
            "report":"report_prompt_path",
            "report_quality":"report_quality_prompt_path",
            "intent_analysis":"intent_analysis_prompt_path",
            "messages_summary":"messages_summary_prompt_path"
            }

if __name__ == "__main__":
    system_prompt = load_prompt(type="system")
   
    print(system_prompt)
