import groq
import json
from fastapi import HTTPException
from backend.config import settings
from backend.models.schemas import PlanResponse

class PlannerAgent:
    def __init__(self):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        self.client = groq.Groq(api_key=settings.groq_api_key)

    def generate_plan(self, task: str) -> PlanResponse:
        system_prompt = f"""You are the Planner Agent for CodePilot, an Autonomous AI Software Engineer.
Your job is to analyze a given coding task and generate a structured implementation plan.
DO NOT invoke or output any tool calls or function calls. Output ONLY a valid JSON object matching the schema below.
Here is the JSON schema you must adhere to:
{PlanResponse.model_json_schema()}
"""
        
        try:
            completion = self.client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task}
                ],
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()
            return PlanResponse.model_validate_json(content)
        except Exception as e:
            raise RuntimeError(f"Failed to generate plan from LLM: {str(e)}")
