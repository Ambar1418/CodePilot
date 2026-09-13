import groq
import json
from backend.config import settings
from backend.models.schemas import DebugRequest, DebugResponse

class DebugAgent:
    def __init__(self):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        self.client = groq.Groq(api_key=settings.groq_api_key)

    def analyze(self, request: DebugRequest) -> DebugResponse:
        system_prompt = f"""You are the Debug Agent for CodePilot.
Your job is to analyze test failures and execution errors and provide a structured diagnosis and fix.
The output MUST exactly match the required structured JSON format.
Here is the JSON schema you must adhere to:
{DebugResponse.model_json_schema()}
"""
        
        user_message = f"""
Task: {request.task}

RAG Context Used:
{request.rag_context}

Code Changes Proposed:
{request.code_result.model_dump_json()}

Sandbox Exit Code: {request.exit_code}
Sandbox STDOUT:
{request.stdout}

Sandbox STDERR:
{request.stderr}
"""

        try:
            completion = self.client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content
            return DebugResponse.model_validate_json(content)
        except Exception as e:
            raise RuntimeError(f"Failed to generate debug analysis from LLM: {str(e)}")
