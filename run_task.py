#!/usr/bin/env python3
import sys
import os
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.orchestrator import CodePilotOrchestrator

def main():
    if len(sys.argv) < 2:
        prompt = "Add a helper function in backend/utils/string_utils.py called truncate_text(text: str, max_length: int = 50) -> str that truncates string to max_length with '...' if longer, and write unit tests for it."
    else:
        prompt = " ".join(sys.argv[1:])

    print("=" * 70)
    print("🚀 Running CodePilot Orchestrator Task from Terminal")
    print(f"Task Prompt: {prompt}")
    print("=" * 70)

    orchestrator = CodePilotOrchestrator()
    state = orchestrator.process_task(task_description=prompt)

    print("\n" + "=" * 70)
    print("📌 TASK EXECUTION SUMMARY")
    print(f"Task ID     : {state.task_id}")
    print(f"Final State : {state.state.value}")
    
    if state.plan:
        print(f"\n📋 Plan Summary: {state.plan.task_summary}")
        if state.plan.steps:
            print("Steps:")
            for s in state.plan.steps:
                print(f"  - {s}")

    if state.code_changes:
        print(f"\n💻 Proposed Code Changes:")
        print(f"Summary: {state.code_changes.summary}")
        print(f"Reasoning: {state.code_changes.reasoning}")
        print(f"Files Modified: {state.code_changes.files_to_modify}")
        print(f"Files Created : {state.code_changes.files_to_create}")
        print(f"Files Deleted : {state.code_changes.files_to_delete}")
        
        if state.code_changes.changes:
            print("\nDiff Details:")
            for change in state.code_changes.changes:
                print(f"\n--- [{change.change_type.upper()}] {change.file_path} ---")
                print(change.diff)

    if state.test_result:
        print(f"\n🧪 Test Results:")
        print(f"Passed    : {state.test_result.passed}")
        print(f"Exit Code : {state.test_result.exit_code}")
        print(f"Output    :\n{state.test_result.output}")

    if state.error_message:
        print(f"\n❌ Error: {state.error_message}")

    print("=" * 70)

if __name__ == "__main__":
    main()
