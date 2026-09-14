#!/usr/bin/env python3
import sys
import os
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator import CodePilotOrchestrator
from backend.models.schemas import OrchestrateRequest
from backend.state.store import StateStore

def main():
    if len(sys.argv) < 2:
        prompt = "Add a helper function in backend/utils/string_utils.py called truncate_text(text: str, max_length: int = 50) -> str that truncates string to max_length with '...' if longer, and write unit tests for it."
    else:
        prompt = " ".join(sys.argv[1:])

    print("=" * 70)
    print("🚀 Running CodePilot Orchestrator Task from Terminal")
    print(f"Task Prompt: {prompt}")
    print("=" * 70)

    repo_path = os.getcwd()
    request = OrchestrateRequest(
        task=prompt,
        repository_path=repo_path,
        sandbox_type="local"
    )

    orchestrator = CodePilotOrchestrator()
    response = orchestrator.run(request)
    change_set = StateStore.get_change(response.change_id)

    print("\n" + "=" * 70)
    print("📌 TASK EXECUTION SUMMARY")
    print(f"Change ID   : {response.change_id}")
    print(f"Final State : {response.status.value if hasattr(response.status, 'value') else response.status}")
    print(f"Attempts    : {response.attempts}")

    if change_set and change_set.code_result:
        code = change_set.code_result
        print(f"\n💻 Proposed Code Changes:")
        print(f"Summary: {code.summary}")
        print(f"Reasoning: {code.reasoning}")
        print(f"Files Modified: {code.files_to_modify}")
        print(f"Files Created : {code.files_to_create}")
        print(f"Files Deleted : {code.files_to_delete}")

    if response.files_changed:
        print(f"\n📄 Files Changed ({len(response.files_changed)}):")
        for f in response.files_changed:
            print(f"  - {f}")

    if response.diff:
        print(f"\n📝 Git Diff:\n{response.diff}")

    if response.validation:
        val = response.validation
        print(f"\n🧪 Validation Result:")
        print(f"Passed    : {val.passed}")
        print(f"Exit Code : {val.exit_code}")
        if val.stdout:
            print(f"Output    :\n{val.stdout}")

    if change_set and change_set.final_diagnosis:
        print(f"\n❌ Final Diagnosis: {change_set.final_diagnosis}")

    print("=" * 70)

if __name__ == "__main__":
    main()
