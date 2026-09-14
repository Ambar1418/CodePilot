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
        system_prompt = """You are the Debug Agent for CodePilot.
Your job is to analyze test failures and execution errors and provide a structured diagnosis and fix.
The output MUST exactly match the required structured JSON format below:

{
  "diagnosis": "<diagnosis>",
  "root_cause": "<root_cause>",
  "affected_files": ["<file_path>"],
  "recommended_changes": ["<change>"],
  "confidence": 0.9,
  "proposed_fix": "<proposed_fix>",
  "updated_instructions": "<updated_instructions>"
}
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

        for attempt in range(5):
            try:
                completion = self.client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=800,
                )
                content = completion.choices[0].message.content
                return DebugResponse.model_validate_json(content)
            except groq.RateLimitError as e:
                if attempt == 4:
                    raise RuntimeError(f"Rate limit exceeded in DebugAgent: {str(e)}")
                import time
                time.sleep(15 * (attempt + 1))
            except Exception as e:
                err_msg = str(e).lower()
                if "413" in err_msg or "429" in err_msg or "rate_limit" in err_msg or "request too large" in err_msg:
                    if attempt == 4:
                        raise RuntimeError(f"Rate limit exceeded in DebugAgent: {str(e)}")
                    import time
                    time.sleep(15 * (attempt + 1))
                    continue
                raise RuntimeError(f"Failed to generate debug analysis from LLM: {str(e)}")
