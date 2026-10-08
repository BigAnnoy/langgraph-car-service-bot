# 检查actual和expected关系的函数
def op_subset(expected, actual):
    missing = set(expected) - set(actual or [])
    return (not missing, f"缺少: {missing}") if missing else (True, f"齐全: {sorted(set(expected))}")
 
def op_disjoint(expected, actual):
    hit = set(expected) & set(actual or [])
    return (not hit, f"不该出现: {hit}") if hit else (True, "无禁用工具")
 
def op_equals(expected, actual):
    return expected == actual, f"期望 {expected} / 实际 {actual}"
 
def op_not_contains(expected, actual):
    hit = [k for k in expected if k in (actual or "")]
    return (not hit, f"关键字泄漏: {hit}") if hit else (True, "未命中关键字")
 
def op_is_empty(expected, actual):
    return not actual, (f"非空: {actual}") if actual else ("空")
 
OPS = {"subset": op_subset, "disjoint": op_disjoint, "equals": op_equals,
       "not_contains": op_not_contains, "is_empty": op_is_empty}


# 定义检查项
SPEC = {
    "expect_tools":      ("subset",   "tools"),
    "expect_no_tools":   ("is_empty", "tools"),
    "expect_scene":      ("equals",   "scene"),
    "expect_interrupted":  ("equals",   "interrupted"),
    "tool_errors":       ("is_empty", "errors"),      # 全局默认
    "leak":              ("not_contains", "content"), # 全局默认
}
# 默认检查项
LEAK_KEYWORDS = ("Traceback", "工具调用失败")
ALWAYS = {"tool_errors": True, "leak": LEAK_KEYWORDS}  


def run_checks(case, actual):
    case = {**ALWAYS, **case}          # 补默认项；case 里同名字段优先，不覆盖你手写的
    results = []
    for field, (op, fact) in SPEC.items():
        if field in case:
            ok, msg = OPS[op](case[field], actual.get(fact))
            results.append((field, ok, msg))
    return results

