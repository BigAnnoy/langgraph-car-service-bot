'''
路径工具类
'''

import os

def get_project_root():
    '''
    获取项目根目录
    '''
    current_file_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(current_file_path))
    return project_root

def get_abs_path(relative_path):
    '''
    获取绝对路径
    '''
    project_root = get_project_root()
    abs_path = os.path.join(project_root, relative_path)
    return abs_path



if __name__ == "__main__":
    print(get_abs_path("config/data.txt"))
