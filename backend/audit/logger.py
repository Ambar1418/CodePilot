"""Audit logger — writes structured events to DB and structured log."""
from __future__ import annotations
import json
import logging
from typing import Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger("codepilot.audit")


class AuditLogger:
    def __init__(self, session=None):
        self._session = session

    def log(
        self,
        event_type: str,
        *,
        change_id: Optional[str] = None,
        user_id: Optional[int] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        attempt_number: int = 0,
        success: bool = True,
        metadata: Optional[dict] = None,
    ) -> None:
        # Always log to structured logger (never expose secrets — caller must sanitize)
        log_record = {
            "event": event_type,
            "change_id": change_id,
            "user_id": user_id,
            "previous_state": previous_state,
            "new_state": new_state,
            "attempt": attempt_number,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            # Strip any secret-looking keys before logging
            safe_meta = {k: v for k, v in metadata.items() if "key" not in k.lower() and "token" not in k.lower() and "password" not in k.lower()}
            log_record["meta"] = safe_meta

        level = logging.INFO if success else logging.WARNING
        logger.log(level, json.dumps(log_record))

        # Write to DB if session is available
        if self._session is not None:
            try:
                from backend.db.models import AuditEvent
                event = AuditEvent(
                    change_id=change_id,
                    user_id=user_id,
                    event_type=event_type,
                    previous_state=previous_state,
                    new_state=new_state,
                    attempt_number=attempt_number,
                    metadata_json=json.dumps(metadata or {}),
                    success=success,
                )
                self._session.add(event)
                self._session.commit()
            except Exception as e:
                logger.error(f"Failed to persist audit event: {e}")


# Convenience no-op logger for use in orchestrator when no session is available
_noop_logger = AuditLogger(session=None)


def get_audit_logger(session=None) -> AuditLogger:
    if session is not None:
        return AuditLogger(session=session)
    return _noop_logger
