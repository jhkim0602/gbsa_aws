# Created: 2026-08-23 22:52
"""Queue attributes shared by the runtime that consumes queues and the script that creates them.

Terraform owns the real queues, so `create_production_runtime` only has to be told what those
queues already say. Locally nothing owns them but `local_infra`, and when the two disagreed the
consumer won on paper and lost in practice: the runtime paced its visibility heartbeat against
300 seconds while the queue expired the lease after the SQS default of 30, so a handler that
outlived 30 seconds -- report generation calls the model once per criterion -- had its message
redelivered mid-flight and a second worker started the same work. Both then raced to insert the
same report and one of them died on the unique constraint.

Reading the numbers from one place is what keeps that from coming back. The values match
`infra/modules/async-workflow/main.tf`, which remains the source of truth for deployments.
"""

from __future__ import annotations

from collections.abc import Mapping

#: Workflow queues, in the order the runtime wires them.
WORKFLOW_QUEUE_NAMES = ("analysis", "media", "reporting", "deletion", "capacity")

#: Media post-processing submits a MediaConvert job and waits; the rest finish sooner.
MEDIA_VISIBILITY_TIMEOUT_SECONDS = 900
DEFAULT_VISIBILITY_TIMEOUT_SECONDS = 300

#: `message_retention_seconds` in the Terraform module: four days for work, fourteen for the
#: dead-letter queue, so a poisoned message survives long enough to be looked at.
QUEUE_MESSAGE_RETENTION_SECONDS = 345_600
DEAD_LETTER_MESSAGE_RETENTION_SECONDS = 1_209_600

#: `var.max_receive_count`. Without a redrive policy a message that always fails is retried
#: until retention expires and then disappears, which is how the local setup behaved.
QUEUE_MAX_RECEIVE_COUNT = 5


def queue_visibility_timeout_seconds(name: str, environment: Mapping[str, str]) -> int:
    """Lease length for one workflow queue, overridable per queue by environment.

    The override exists so a deployment can lengthen a lease without a code change; the default
    has to agree with whatever created the queue, which is why both callers ask this function.
    """
    default = (
        MEDIA_VISIBILITY_TIMEOUT_SECONDS if name == "media" else DEFAULT_VISIBILITY_TIMEOUT_SECONDS
    )
    return int(environment.get(f"SQS_{name.upper()}_VISIBILITY_TIMEOUT_SECONDS", str(default)))


def dead_letter_queue_name(queue_name: str) -> str:
    """Terraform names the dead-letter queue after its work queue; local runs must match."""
    return f"{queue_name}-dlq"
