import sqlite3
from utils.path_tool import get_abs_path
from datetime import datetime
import uuid
from utils.config_handler import business_config

class SessionService:
    def __init__(self):
        self.sqlite_path=get_abs_path(business_config["business_db"])
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {business_config['session_table_name']} (session_id TEXT PRIMARY KEY,title TEXT,user_id TEXT,create_time TEXT)")
            conn.commit()

    # 初始化新会话,加入数据库记录
    def create_session(self,user_id:str,title:str=None):
        session_id = uuid.uuid4().hex
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(f"INSERT INTO {business_config['session_table_name']} (session_id,title,user_id,create_time) VALUES (?,?,?,?)",((session_id,title,user_id,datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))
            conn.commit()
        return session_id

    # 查询用户所有会话
    def list_user_session(self,user_id:str)->list:
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.execute(f"SELECT session_id,title,create_time FROM {business_config['session_table_name']} WHERE user_id=?",(user_id,))
            sessions = cursor.fetchall()
            session_list=[]
            for session in sessions:
                session_id=session[0]
                title=session[1]
                create_time=session[2]
                session_list.append({"session_id":session_id,"title":title,"create_time":create_time})
            return session_list

