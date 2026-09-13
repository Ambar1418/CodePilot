import groq
import json
import os
from pathlib import Path
from backend.config import settings
from backend.models.schemas import CodeRequest, CodeResponse, CodeChange
from backend.tools.registry import registry
import backend.tools.filesystem  # register filesystem tools
import backend.tools.search      # register search tools
import backend.tools.terminal    # register terminal tools
from backend.tools.filesystem import get_workspace_root

class CoderAgent:
    def __init__(self):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        self.client = groq.Groq(api_key=settings.groq_api_key)
        self.max_iterations = 15

    def generate_code(self, request: CodeRequest) -> CodeResponse:
        system_prompt = f"""You are the Autonomous Coding Agent for CodePilot, a senior software engineer.
Your job is to receive a coding task, an implementation plan, and initial code context, and execute the plan.
You have access to safe tools for exploring the filesystem, searching code, editing files, running commands, and running tests.

CRITICAL RULES:
1. Work iteratively. You can explore, run tests, see failures, fix code, and run tests again.
2. Produce minimal, focused changes.
3. NEVER guess file contents. Always read them before editing.
4. When you are completely done and all tests pass (or if you hit a dead end), you MUST call the `submit_final_code` tool to conclude the task.
5. You CANNOT submit final code unless you have successfully executed tests and they passed (Exit Code: 0).
"""
        
        essential_tool_names = {"read_file", "write_file", "execute_command", "run_tests"}
        tools = [t for t in registry.get_tools_schema() if t.get("function", {}).get("name") in essential_tool_names]
        
        tools.append({
            "type": "function",
            "function": {
                "name": "submit_final_code",
                "description": "Submit the final proposed code changes and conclude the task.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "Summary of changes made"},
                        "files_to_modify": {"type": "array", "items": {"type": "string"}},
                        "files_to_create": {"type": "array", "items": {"type": "string"}},
                        "files_to_delete": {"type": "array", "items": {"type": "string"}},
                        "reasoning": {"type": "string", "description": "Technical reasoning"}
                    },
                    "required": ["summary", "files_to_modify", "reasoning"]
                }
            }
        })

        plan_summary = request.plan.task_summary
        plan_steps = "\n".join(f"- {step}" for step in request.plan.steps) if getattr(request.plan, 'steps', None) else ""
        plan_text = f"{plan_summary}\nSteps:\n{plan_steps}" if plan_steps else plan_summary

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {request.task}\n\nPlan:\n{plan_text}\n\nInitial Context:\n{request.code_context}"}
        ]

        iterations = 0
        consecutive_errors = 0
        
        # Programmatic Gate State
        tests_run = False
        tests_passed = False
        last_test_output = ""
        
        # File Verification State
        root = get_workspace_root()
        initial_files = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("__pycache__", "venv")]
            for f in filenames:
                if not f.startswith("."):
                    full_path = Path(dirpath) / f
                    try:
                        rel_path = str(full_path.relative_to(root))
                        stat = full_path.stat()
                        initial_files[rel_path] = (stat.st_mtime, stat.st_size)
                    except:
                        pass
        
        while iterations < self.max_iterations:
            iterations += 1
            if consecutive_errors > 3:
                raise RuntimeError("Too many consecutive tool errors. Aborting.")
                
            try:
                completion = self.client.chat.completions.create(
                    model=settings.llm_model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
            except Exception as e:
                raise RuntimeError(f"API Error: {str(e)}")
                
            response_message = completion.choices[0].message
            messages.append(response_message)
            
            if not response_message.tool_calls:
                # Agent spoke instead of calling a tool. Prod it.
                messages.append({
                    "role": "user", 
                    "content": "Please continue executing tools or call 'submit_final_code' when finished."
                })
                continue
                
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps({"error": "Invalid JSON arguments."})
                    })
                    consecutive_errors += 1
                    continue
                    
                if function_name == "submit_final_code":
                    if not tests_run or not tests_passed:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps({
                                "success": False,
                                "tool": "submit_final_code",
                                "error": "Cannot submit final code because tests have not passed.",
                                "requirement": "Run tests and fix all failures before submitting."
                            })
                        })
                        continue
                    else:
                        # Tests passed, allow submission
                        args.setdefault("changes", [])
                        args.setdefault("files_to_create", [])
                        args.setdefault("files_to_delete", [])
                        args.setdefault("testing_notes", "Passed automated unit tests")
                        parsed = CodeResponse.model_validate(args)
                        parsed.test_execution_result = last_test_output
                        
                        try:
                            from backend.tools.git_diff import get_git_changes
                            git_data = get_git_changes(root)
                            
                            parsed.files_to_modify = git_data["modified"]
                            parsed.files_to_create = git_data["created"]
                            parsed.files_to_delete = git_data["deleted"]
                            
                            actual_changes = []
                            for f in git_data["modified"]:
                                actual_changes.append(CodeChange(file_path=f, change_type="modify", description="Modified (Git)", diff=git_data["diffs"].get(f, "")))
                            for f in git_data["created"]:
                                actual_changes.append(CodeChange(file_path=f, change_type="create", description="Created (Git)", diff=git_data["diffs"].get(f, "")))
                            for f in git_data["deleted"]:
                                actual_changes.append(CodeChange(file_path=f, change_type="delete", description="Deleted (Git)", diff=git_data["diffs"].get(f, "")))
                                
                            parsed.changes = actual_changes
                            
                        except Exception:
                            # Verify file changes programmatically using fallback
                            actual_modified = []
                            actual_created = []
                            for dirpath, dirnames, filenames in os.walk(root):
                                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("__pycache__", "venv")]
                                for f in filenames:
                                    if not f.startswith("."):
                                        full_path = Path(dirpath) / f
                                        try:
                                            rel_path = str(full_path.relative_to(root))
                                            stat = full_path.stat()
                                            current_mtime = stat.st_mtime
                                            current_size = stat.st_size
                                            if rel_path not in initial_files:
                                                actual_created.append(rel_path)
                                            else:
                                                init_mtime, init_size = initial_files[rel_path]
                                                if current_mtime != init_mtime or current_size != init_size:
                                                    actual_modified.append(rel_path)
                                        except:
                                            pass
                            
                            parsed.files_to_modify = actual_modified
                            parsed.files_to_create = actual_created
                            
                            # For fallback, we don't have deletions easily without checking all initial_files keys.
                            actual_deleted = []
                            for f in initial_files:
                                if not (root / f).exists():
                                    actual_deleted.append(f)
                            parsed.files_to_delete = actual_deleted
                            
                            # Construct simple changes without raw diff
                            actual_changes = []
                            for f in actual_modified:
                                actual_changes.append(CodeChange(file_path=f, change_type="modify", description="Modified (Fallback)", diff=""))
                            for f in actual_created:
                                actual_changes.append(CodeChange(file_path=f, change_type="create", description="Created (Fallback)", diff=""))
                            for f in actual_deleted:
                                actual_changes.append(CodeChange(file_path=f, change_type="delete", description="Deleted (Fallback)", diff=""))
                            
                            parsed.changes = actual_changes

                        return parsed
                    
                # Execute tool
                result = registry.execute(function_name, args)
                if not result["success"]:
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0
                    if function_name == "run_tests":
                        tests_run = True
                        last_test_output = result.get("result", "")
                        if "Exit Code: 0" in last_test_output:
                            tests_passed = True
                        else:
                            tests_passed = False
                            
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps(result)
                })

        raise RuntimeError(f"Max iterations ({self.max_iterations}) reached without submitting final code.")
