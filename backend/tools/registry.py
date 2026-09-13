# registry.py
from typing import Callable, Dict, Any, List

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, dict] = {}
        self.functions: Dict[str, Callable] = {}

    def register(self, name: str, description: str, parameters: dict, func: Callable):
        self.tools[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            }
        }
        self.functions[name] = func

    def get_tools_schema(self) -> List[dict]:
        return list(self.tools.values())

    def execute(self, name: str, args: dict) -> dict:
        if name not in self.functions:
            return {
                "success": False,
                "tool": name,
                "result": None,
                "error": f"Tool '{name}' not found."
            }
        
        try:
            result = self.functions[name](**args)
            return {
                "success": True,
                "tool": name,
                "result": result,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "tool": name,
                "result": None,
                "error": str(e)
            }

registry = ToolRegistry()
