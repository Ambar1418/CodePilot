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
The output MUST exactly match the required structured JSON format.
Here is the JSON schema you must adhere to:
{PlanResponse.model_json_schema()}
"""
        
        try:
            completion = self.client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task}
                ],
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content
            return PlanResponse.model_validate_json(content)
        except Exception as e:
            raise RuntimeError(f"Failed to generate plan from LLM: {str(e)}")
