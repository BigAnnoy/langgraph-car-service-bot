from utils.config_handler import memory_config
def append_memory(store,user_id,category,attr,value):
    ns=('long_term_memory',user_id,category)
    item = store.get(ns,attr)
    items=item.value.get("value") if item else None
    if not isinstance (items, list ):
        items=[]
    if value not in items:
        items.append(value)
    while len(items)>memory_config["append_max_length"] and len(items)>1:
        items.pop(0)
    store.put(('long_term_memory',user_id,category),key=attr,value={"value":items})

def render_value(raw):
    if isinstance(raw,list):
        str_raw=""
        x=1
        for i in raw:
            str_raw+=f"{x}.{i}\n"
            x+=1
        return str_raw
    return raw