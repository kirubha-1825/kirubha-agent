"""
sri_master_agent.py - Universal Master Agent Module for Multi-AI Orchestration.
Provides:
    - SriUniversalMasterAgent
    - execute_universal_task(input_key, work_area, task_description)
"""

from sri_universal_master_agent import SriUniversalMasterAgent

# Default singleton instance for module-level operations
_default_master_agent = SriUniversalMasterAgent()


def execute_universal_task(
    input_key: str = "SRI_AUTH_SEC_948f2b7a0c91825",
    work_area: str = "workspace/student_learning_hub",
    task_description: str = "SRI Master Agent Task",
    *args,
    **kwargs
):
    """
    Module-level function matching execute_universal_task signature with all 3 required arguments:
    input_key, work_area, and task_description.
    """
    key = input_key or getattr(_default_master_agent, "master_key", "SRI_AUTH_SEC_948f2b7a0c91825")
    area = work_area or "workspace/student_learning_hub"
    desc = task_description or (args[0] if args else "SRI Master Agent Task")
    return _default_master_agent.execute_universal_task(
        input_key=key,
        work_area=area,
        task_description=desc,
        *args,
        **kwargs
    )


__all__ = ["SriUniversalMasterAgent", "execute_universal_task", "_default_master_agent"]
