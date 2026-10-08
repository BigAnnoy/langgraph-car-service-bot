import streamlit as st
from agent.graph_agent import GraphAgent
from services.session_service import SessionService
from utils.logger_handler import logger
from dotenv import load_dotenv
load_dotenv()

# 模拟用户ID
if "user_id" not in st.session_state:
    # st.session_state["user_id"]=random.choice(["1001","1002","1003","1004", "1005","1006","1007","1008","1009","1010"])
    st.session_state["user_id"]="1010"
st.title("智能车管家")
st.write(f"您好，用户：{st.session_state['user_id']}")
st.divider()

# 根据用户ID获取线程ID
if "thread_id" not in st.session_state:
    session_service=SessionService()
    history_session_list=session_service.list_user_session(st.session_state["user_id"])
    if history_session_list:
        st.session_state["thread_id"]=history_session_list[-1]["session_id"]
    else:
        st.session_state["thread_id"]=session_service.create_session(st.session_state["user_id"])

# 显示当前线程ID,用于调试
st.write(f"当前线程ID：{st.session_state['thread_id']}")


# 初始化GraphAgent
if "GraphAgent" not in st.session_state:
    st.session_state["GraphAgent"]=GraphAgent()

# 初始化对话历史
if "history" not in st.session_state:
    st.session_state["history"]=[{"role":"assistant","content":"你好，请输入您的问题"}]

for msg in st.session_state["history"]:
    st.chat_message(msg["role"]).write(msg["content"])

# 定义中断捕获、流式输出缓存函数
def capture(generator,cache_list):
    for chunk in generator:
        if "process" in chunk:
            st.toast(chunk["process"])
        elif "content" in chunk:
            cache_list.append(chunk["content"])
            yield chunk["content"]
        elif "interrupt" in chunk:
            st.session_state["interrupt"]=chunk["interrupt"]
            break
if "interrupt" not in st.session_state:
    st.session_state["interrupt"]=None

# 主流程
if not st.session_state["interrupt"] and "pending_resume" not in st.session_state:
    prompt=st.chat_input("请输入您的问题")
    if prompt:
        st.chat_message("user").write(prompt)
        with st.spinner("思考中"):
            st.session_state["history"].append({"role":"user","content":prompt})
            resp_stream=st.session_state["GraphAgent"].execute_stream(user_id=st.session_state["user_id"],thread_id=st.session_state["thread_id"],query=prompt)
            ai_res_list=[]
            st.session_state["interrupt"]=None
            st.chat_message("ai").write_stream(capture(resp_stream,ai_res_list))
            if ai_res_list:
                st.session_state["history"].append({"role":"assistant","content":"".join(ai_res_list)})

# 用户中断处理
if st.session_state["interrupt"]:
    # 展示中断选项
    resume_decision={}
    st.chat_message("assistant").write(st.session_state["interrupt"])
    choice = st.segmented_control( "审阅意见" ,[ "接受" , "修改" , "取消" ],default= "接受" ,selection_mode= "single" ,)

    choice_map={"接受":"accept","取消":"cancel","修改":"edit"}
    edit_text = st.text_area("请写入修改建议", disabled=(choice != "修改"))
    # 提交后刷新页面
    if st.button("提交"):
        if choice_map[choice]== "edit" and not (edit_text or "" ).strip():
            st.warning( "请先填写修改建议" )
            st.stop()
        resume_decision["user_decision"]=choice_map[choice]
        if choice_map[choice]=="edit":
            resume_decision["user_edit_content"]=edit_text.strip()
        st.session_state["pending_resume"]=resume_decision
        st.session_state["interrupt"]=None
        st.rerun()

# resume 流程
if "pending_resume" in st.session_state:
    resume_decision=st.session_state.pop("pending_resume")
    # 执行恢复流
    with st.spinner("思考中"):
        ai_res_list=[]
        rsm_stream=st.session_state["GraphAgent"].resume_stream(user_id=st.session_state["user_id"],thread_id=st.session_state["thread_id"],resume_decision=resume_decision)
        st.chat_message("ai").write_stream(capture(rsm_stream,ai_res_list))
    if ai_res_list:
        st.session_state["history"].append({"role":"assistant","content":"".join(ai_res_list)})
    st.rerun()
