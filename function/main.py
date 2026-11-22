import hashlib
import ipaddress
import json
import logging
import os
import shutil
import socket
import tempfile
import uuid
import zipfile
from functools import lru_cache
from urllib.parse import urljoin, urlsplit, urlunsplit

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from urllib3 import HTTPConnectionPool, HTTPSConnectionPool, Timeout

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def archive_key(message):
    timestamp_ms = int(message["attributes"]["SentTimestamp"])
    if not 0 <= timestamp_ms < 2**48:
        raise ValueError("Invalid YMQ message timestamp")

    digest = hashlib.sha256(message["message_id"].encode("ascii")).digest()
    random_bits = int.from_bytes(digest[:10], "big")
    value = (
        (timestamp_ms << 80)
        | (7 << 76)
        | (((random_bits >> 62) & 0xFFF) << 64)
        | (0b10 << 62)
        | (random_bits & ((1 << 62) - 1))
    )
    return f"{uuid.UUID(int=value)}.zip"


def source_connection(url):
    address = urlsplit(url)
    if address.scheme not in {"http", "https"} or not address.hostname:
        raise ValueError("The source must be an HTTP or HTTPS URL")
    if address.username is not None or address.password is not None:
        raise ValueError("The source URL must not contain credentials")

    hostname = address.hostname.encode("idna").decode("ascii")
    https = address.scheme == "https"
    port = address.port or (443 if https else 80)
    records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)

    ips = sorted({ipaddress.ip_address(record[4][0]) for record in records}, key=lambda ip: ip.version)
    public_ip = next((ip for ip in ips if ip.is_global and not ip.is_multicast), None)
    if public_ip is None:
        raise ValueError("The source host must resolve to a public IP address")

    timeout = Timeout(connect=8, read=30)
    if https:
        pool = HTTPSConnectionPool(
            str(public_ip), port, timeout=timeout, server_hostname=hostname, assert_hostname=hostname
        )
    else:
        pool = HTTPConnectionPool(str(public_ip), port, timeout=timeout)
    host_header = f"[{hostname}]" if ":" in hostname else hostname
    if address.port is not None:
        host_header = f"{host_header}:{port}"
    target = urlunsplit(("", "", address.path or "/", address.query, ""))
    return pool, target, host_header


def make_zip(url, filename, output):
    for _ in range(6):
        pool, target, host = source_connection(url)
        with pool, pool.request(
            "GET",
            target,
            headers={"Host": host, "Accept-Encoding": "identity"},
            preload_content=False,
            retries=False,
            redirect=False,
        ) as response:
            if response.status in {301, 302, 303, 307, 308} and response.headers.get("Location"):
                url = urljoin(url, response.headers["Location"])
                continue
            if response.status not in {200, 204}:
                raise RuntimeError(f"Source download failed with HTTP {response.status}")
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                with archive.open(filename, "w", force_zip64=True) as member:
                    shutil.copyfileobj(response, member, length=256 * 1024)
            return
    raise RuntimeError("Too many source redirects")


@lru_cache(maxsize=1)
def storage_clients():
    session = boto3.session.Session(
        aws_access_key_id=os.environ["WORKER_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["WORKER_SECRET_KEY"],
        region_name=os.environ["CLOUD_REGION"],
    )
    config = Config(
        connect_timeout=5,
        read_timeout=30,
        retries={"mode": "standard", "total_max_attempts": 3},
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
        s3={"addressing_style": "path"},
    )
    storage = session.client("s3", endpoint_url=os.environ["STORAGE_API_ENDPOINT"], config=config)
    database = session.client("dynamodb", endpoint_url=os.environ["DOCUMENT_API_ENDPOINT"], config=config)
    return storage, database


def ensure_archive(storage, bucket, key, url, filename):
    try:
        storage.head_object(Bucket=bucket, Key=key)
        return
    except ClientError as error:
        if error.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            raise

    with tempfile.TemporaryFile() as payload:
        make_zip(url, filename, payload)
        size = payload.tell()
        payload.seek(0)
        try:
            storage.put_object(
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentLength=size,
                ContentType="application/zip",
                ContentDisposition=f'attachment; filename="{key}"',
                IfNoneMatch="*",
            )
        except ClientError as error:
            if error.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
                raise


def handler(event, context):
    (record,) = event["messages"]
    message = record["details"]["message"]
    task = json.loads(message["body"])
    filename, url = task["name"], task["url"]
    if (
        not isinstance(filename, str)
        or not 1 <= len(filename) <= 255
        or filename in {".", ".."}
        or any(char in "/\\:" or ord(char) < 32 for char in filename)
    ):
        raise ValueError("The task must contain a plain filename")

    key = archive_key(message)
    bucket = os.environ["ARCHIVE_BUCKET"]
    table = os.environ["ARCHIVE_TABLE"]
    key_attribute = os.environ["ARCHIVE_KEY_ATTRIBUTE"]
    storage, database = storage_clients()

    ensure_archive(storage, bucket, key, url, filename)
    database.put_item(
        TableName=table,
        Item={key_attribute: {"S": key}, "name": {"S": filename}, "url": {"S": url}},
    )
    logger.info("Archive stored: %s", key)
    return {"key": key}
