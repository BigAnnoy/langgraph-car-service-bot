from utils.config_handler import business_config, memory_config
from agent.graph_agent import GraphAgent
from utils.path_tool import get_abs_path
import json
from services.session_service import SessionService
from evals.trace_handler import ToolTrace
import sys
import os
import glob
from evals.evaluators import run_checks
business_config[ "business_db" ] = "evals/databases/eval_business.db" 
memory_config[ "memory_db" ]    = "evals/databases/eval_memory.db"

def capture_stream(generator):
    main_content=[]
    process_content=[]
    interrupt=[]
    for chunk in generator:
        if "process" in chunk:
            process_content.append(chunk["process"])
        elif "content" in chunk:
            main_content.append(chunk["content"])
        elif "interrupt" in chunk:
            interrupt.append(chunk["interrupt"])
            break
    return main_content,process_content,interrupt

def reset_eval_databases():
    # 只允许删评测库
    for name in (business_config["business_db"], memory_config["memory_db"]):
        if "eval" not in os.path.basename(name):
            raise RuntimeError(f"拒绝删除非评测库: {name}")
    # 清空评测库
    for name in (business_config["business_db"], memory_config["memory_db"]):
        for path in glob.glob(get_abs_path(name) + "*"):
            os.remove(path)
            print("removed", os.path.basename(path))

def test():
    reset_eval_databases()
    graph_agent=GraphAgent()
    session_service=SessionService()
    cases=[]
    with open(get_abs_path("evals/cases.jsonl"),encoding="UTF-8") as f :
        for line in f:
            case=json.loads(line)
            cases.append(case)
    failed, skipped = [], []
    for case in cases:

        if not case.get("enable"):
            skipped.append(case["id"])
            continue
        case_tool_trace=ToolTrace()
        case_user_id =  case.get("user_id","1001")
        case_thread_id = session_service.create_session(case_user_id)
        step_one_result = graph_agent.execute_stream(user_id=case_user_id,thread_id=case_thread_id,query=case["query"],callbacks=[case_tool_trace])
        step_one={}
        step_one["main_content"],step_one["process_content"],step_one["interrupt"] = capture_stream(step_one_result)
       
        # 恢复执行，根据用户决策
        step_two={}
        if step_one["interrupt"]:    
            resume_decision={"user_decision":case.get("resume_decision","accept"),"user_edit_content":case.get("user_edit_content","")}
            step_two_result = graph_agent.resume_stream(user_id=case_user_id,thread_id=case_thread_id,resume_decision=resume_decision,callbacks=[case_tool_trace])     
            step_two["main_content"],step_two["process_content"],step_two["interrupt"] = capture_stream(step_two_result)
        # 二次中断，写死accept决策
        step_three={}
        if step_two.get("interrupt"):
            resume_decision={"user_decision":"accept","user_edit_content":""}
            step_three_result=graph_agent.resume_stream(user_id=case_user_id,thread_id=case_thread_id,resume_decision=resume_decision,callbacks=[case_tool_trace])
            step_three["main_content"],step_three["process_content"],step_three["interrupt"]=capture_stream(step_three_result)  
        # 填入case_result
        case_result={}
        case_result["tools"]=list(case_tool_trace.tools)
        case_result["errors"]=list(case_tool_trace.errors)
        case_result["nodes"]=list(case_tool_trace.nodes)
        case_result["interrupted"]=bool(step_one["interrupt"])
        case_result["scene"]=("report" if "report_scene_subgraph" in case_result["nodes"]
                          else "chat" if "chat_scene_subgraph" in case_result["nodes"]
                          else "unknown")
        case_result["content"]="\n".join(step_one["main_content"])+"\n".join(step_one["interrupt"])+"\n".join(step_one["process_content"])
        case_result["content"]+="\n".join(step_two.get("main_content",[]))+"\n".join(step_two.get("process_content",[]))+"\n".join(step_two.get("interrupt",[]))
        case_result["content"]+="\n".join(step_three.get("main_content",[]))+"\n".join(step_three.get("process_content",[]))+"\n".join(step_three.get("interrupt",[]))
        # 检查case_result
        case_failed = False
        for name, ok, msg in run_checks(case, case_result):
            print(f"[{case['id']}][{name}] {'PASS' if ok else 'FAIL'} {msg}")
            case_failed = case_failed or not ok
        if case_failed:
            failed.append(case["id"])   
    print("="*50+"数据统计"+"="*50)
    print(f"failed: {len(failed)}")
    print(f"skipped: {len(skipped)}")
    print(f"total: {len(cases)}")
    print(f"success: {len(cases)-len(failed)-len(skipped)}")
    print("="*52+"="*52)
    sys.exit(1 if failed else 0)
if __name__ == "__main__":
    test()