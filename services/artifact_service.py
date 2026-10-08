import sqlite3
from utils.path_tool import get_abs_path
from datetime import datetime
from utils.config_handler import business_config
import re
class ArtifactService:
    def __init__(self):
        self.sqlite_path=get_abs_path(business_config["business_db"])
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {business_config['artifact_table_name']}" 
                        "(artifact_id INTEGER PRIMARY KEY AUTOINCREMENT"
                        ",user_id TEXT,category TEXT,title TEXT,content TEXT,create_time TEXT)")
            conn.commit()

    # 新产物,加入数据库记录
    def save_artifact(self,user_id:str,category:str,title:str=None,content:str=None):
        if not title and content:
            m = re. match ( r"#+\s*(.+)" , content.lstrip())
            title = m.group( 1 ).strip() if m else category
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor=conn.execute(f"INSERT INTO {business_config['artifact_table_name']} (user_id,category,title,content,create_time) VALUES (?,?,?,?,?)",
                        (user_id,category,title,content,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            artifact_id = cursor.lastrowid
        return {"result":"success","artifact_id":artifact_id}

    # 查询用户产物，返回粗略信息
    def query_artifact_overview(self,user_id:str,category:str)->list:
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.execute(f"SELECT artifact_id,category,title,create_time FROM {business_config['artifact_table_name']} WHERE user_id=? AND category=?",(user_id,category))
            artifacts = cursor.fetchall()
            artifact_list=[]
            for artifact in artifacts:
                artifact_id=artifact[0]
                category=artifact[1]
                title=artifact[2]
                create_time=artifact[3]
                artifact_list.append({"artifact_id":artifact_id,"category":category,"title":title,"create_time":create_time})
            return artifact_list

    # 查询用户产物，返回详细信息
    def query_artifact_detail(self,user_id:str,artifact_id:int)->dict|None:
        """
        获取用户产物详情
        :param user_id: 用户ID
        :param artifact_id: 产物ID
        :return: 用户产物详情
        """
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.execute(f"SELECT artifact_id,category,title,content,create_time FROM {business_config['artifact_table_name']} WHERE artifact_id=? AND user_id=?",(artifact_id,user_id))
            artifact = cursor.fetchone()
            if artifact:
                artifact_id=artifact[0]
                category=artifact[1]
                title=artifact[2]
                content=artifact[3]
                create_time=artifact[4] 
                artifact_detail={"artifact_id":artifact_id,"category":category,"title":title,"content":content,"create_time":create_time}
                return artifact_detail
            else:
                return None

        
