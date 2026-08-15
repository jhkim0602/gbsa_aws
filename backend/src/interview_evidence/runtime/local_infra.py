from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Protocol, cast

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]


class LocalS3Client(Protocol):
    def head_bucket(self, **kwargs: object) -> object: ...

    def create_bucket(self, **kwargs: object) -> object: ...

    def put_bucket_cors(self, **kwargs: object) -> object: ...


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
    for name in ("analysis", "media", "reporting", "deletion"):
        sqs.create_queue(QueueName=_required(values, f"LOCAL_{name.upper()}_QUEUE_NAME"))

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

    _ensure_search_index(
        endpoint=_required(values, "OPENSEARCH_ENDPOINT"),
        index_name=_required(values, "OPENSEARCH_INDEX_NAME"),
    )


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


def _ensure_search_index(*, endpoint: str, index_name: str) -> None:
    url = f"{endpoint.rstrip('/')}/{index_name}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, method="HEAD"),
            timeout=5,
        ) as response:
            if response.status == 200:
                return
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    mapping = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "company_id": {"type": "keyword"},
                "applicant_id": {"type": "keyword"},
                "source_id": {"type": "keyword"},
                "text": {"type": "text"},
                "vector": {
                    "type": "knn_vector",
                    "dimension": 1024,
                },
                "symbols": {"type": "keyword"},
                "locator": {"type": "object", "enabled": True},
                "ownership_confidence": {"type": "float"},
            }
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(mapping, separators=(",", ":")).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status not in {200, 201}:
            raise RuntimeError("local search index initialization failed")


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required local infrastructure setting is missing: {name}")
    return value.strip()


def main() -> None:
    initialize_local_infrastructure()


if __name__ == "__main__":
    main()
