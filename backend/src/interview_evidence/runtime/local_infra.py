from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Protocol, cast

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]

from interview_evidence.runtime.queue_topology import (
    DEAD_LETTER_MESSAGE_RETENTION_SECONDS,
    QUEUE_MESSAGE_RETENTION_SECONDS,
    WORKFLOW_QUEUE_NAMES,
    dead_letter_queue_name,
    queue_max_receive_count,
    queue_visibility_timeout_seconds,
)


class LocalS3Client(Protocol):
    def head_bucket(self, **kwargs: object) -> object: ...

    def create_bucket(self, **kwargs: object) -> object: ...

    def put_bucket_cors(self, **kwargs: object) -> object: ...


class LocalSqsClient(Protocol):
    def create_queue(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_queue_attributes(self, **kwargs: object) -> Mapping[str, object]: ...

    def set_queue_attributes(self, **kwargs: object) -> object: ...


def initialize_local_infrastructure(
    environment: Mapping[str, str] | None = None,
) -> None:
    values = dict(os.environ if environment is None else environment)
    region = _required(values, "AWS_REGION")
    aws_endpoint = _required(values, "AWS_ENDPOINT_URL")
    s3 = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=aws_endpoint,
        config=Config(
            connect_timeout=3,
            read_timeout=3,
            retries={"max_attempts": 1},
            s3={"addressing_style": "path"},
        ),
    )
    for bucket in (
        _required(values, "SOURCE_BUCKET"),
        _required(values, "MEDIA_BUCKET"),
    ):
        _ensure_bucket(cast(LocalS3Client, s3), bucket, region=region)

    sqs = boto3.client(
        "sqs",
        region_name=region,
        endpoint_url=aws_endpoint,
        config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1}),
    )
    for name in WORKFLOW_QUEUE_NAMES:
        _ensure_workflow_queue(
            cast(LocalSqsClient, sqs),
            name=name,
            queue_name=_required(values, f"LOCAL_{name.upper()}_QUEUE_NAME"),
            environment=values,
        )

    dynamodb = boto3.client(
        "dynamodb",
        region_name=region,
        endpoint_url=_required(values, "DYNAMODB_ENDPOINT_URL"),
        config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1}),
    )
    table_name = _required(values, "DYNAMODB_TABLE_NAME")
    try:
        dynamodb.describe_table(TableName=table_name)
    except Exception:
        dynamodb.create_table(
            TableName=table_name,
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )


def _ensure_workflow_queue(
    client: LocalSqsClient,
    *,
    name: str,
    queue_name: str,
    environment: Mapping[str, str],
) -> None:
    """Create the work queue and its dead-letter queue, then assert the attributes on both.

    Attributes are set after creation rather than passed to `create_queue`, because the queue
    usually exists already: `create_queue` leaves an existing queue alone when the attributes
    match and fails when they differ, so neither branch would correct a queue created before
    this function did anything. `set_queue_attributes` converges either way, which also means
    an existing 30-second local queue is repaired the next time `make up` runs.
    """
    dead_letter_url = _queue_url(client.create_queue(QueueName=dead_letter_queue_name(queue_name)))
    client.set_queue_attributes(
        QueueUrl=dead_letter_url,
        Attributes={"MessageRetentionPeriod": str(DEAD_LETTER_MESSAGE_RETENTION_SECONDS)},
    )
    dead_letter_arn = _queue_attribute(
        client.get_queue_attributes(QueueUrl=dead_letter_url, AttributeNames=["QueueArn"]),
        "QueueArn",
    )
    queue_url = _queue_url(client.create_queue(QueueName=queue_name))
    client.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={
            "VisibilityTimeout": str(queue_visibility_timeout_seconds(name, environment)),
            "MessageRetentionPeriod": str(QUEUE_MESSAGE_RETENTION_SECONDS),
            "RedrivePolicy": json.dumps(
                {
                    "deadLetterTargetArn": dead_letter_arn,
                    "maxReceiveCount": queue_max_receive_count(name, environment),
                }
            ),
        },
    )


def _queue_url(response: Mapping[str, object]) -> str:
    url = response.get("QueueUrl")
    if not isinstance(url, str) or not url:
        raise RuntimeError("SQS did not return a queue URL")
    return url


def _queue_attribute(response: Mapping[str, object], name: str) -> str:
    attributes = response.get("Attributes")
    value = attributes.get(name) if isinstance(attributes, Mapping) else None
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"SQS did not return the {name} attribute")
    return value


def _ensure_bucket(client: LocalS3Client, bucket: str, *, region: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        create: dict[str, object] = {"Bucket": bucket}
        if region != "us-east-1":
            create["CreateBucketConfiguration"] = {
                "LocationConstraint": region,
            }
        client.create_bucket(**create)
    client.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "HEAD", "PUT"],
                    "AllowedOrigins": [
                        "http://localhost:5173",
                        "http://localhost:5174",
                        "http://127.0.0.1:5173",
                        "http://127.0.0.1:5174",
                    ],
                    "ExposeHeaders": ["ETag", "x-amz-checksum-sha256"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required local infrastructure setting is missing: {name}")
    return value.strip()


def main() -> None:
    initialize_local_infrastructure()


if __name__ == "__main__":
    main()
