from langgraph.callbacks import BaseCallbackHandler
class ToolTrace(BaseCallbackHandler):
    def __init__(self):
        self.tools=[]
        self.errors=[]
        self.nodes=[]

    def on_tool_start(self,serialized,input_str,**kwargs):
        self.tools.append(serialized.get("name"))
 
    def on_tool_error(self,error,**kwargs):
        self.errors.append(str(error))

    def on_chain_start(self, serialized, inputs, **kwargs): 
        node = (kwargs.get("metadata") or {}).get("langgraph_node")
        if node and node not in self.nodes:
            self.nodes.append(node)  