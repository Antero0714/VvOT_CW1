import argparse
import io
import json
import time
import uuid
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(url, task=None):
    headers = {"Accept-Encoding": "identity"}
    data = None
    if task is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(task).encode("utf-8")
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=30) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except HTTPError as error:
        with error:
            return error.code, error.read(), error.headers.get_content_type()


def expect_status(label, expected, response):
    status, body, content_type = response
    if status != expected:
        raise RuntimeError(f"{label}: expected HTTP {expected}, received {status}: {body[:300]!r}")
    return body, content_type


def wait_for_archive(api, task, wait_seconds):
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        body, _ = expect_status("GET /archives", 200, request(f"{api}/archives"))
        archives = json.loads(body)
        if not isinstance(archives, list):
            raise RuntimeError("GET /archives did not return a JSON array")
        for archive in archives:
            if archive["name"] == task["name"] and archive["url"] == task["url"]:
                return archive
        time.sleep(3)
    raise RuntimeError("Archive did not appear in YDB in time. Check the function and queue.")


def smoke(api, source, wait_seconds, output):
    expected_file, _ = expect_status("Source file", 200, request(source))
    task = {"name": f"demo-{uuid.uuid4().hex[:10]}.txt", "url": source}
    expect_status("POST /tasks", 202, request(f"{api}/tasks", task))
    print(f"PASS POST /tasks → 202, file: {task['name']}", flush=True)

    archive = wait_for_archive(api, task, wait_seconds)
    key = archive["key"]
    archive_id = uuid.UUID(key.removesuffix(".zip"))
    if archive_id.version != 7 or key != f"{archive_id}.zip":
        raise RuntimeError(f"Unexpected archive key: {key}")
    print(f"PASS GET /archives → 200, key: {key}", flush=True)

    body, _ = expect_status("GET /archives/{key}", 200, request(f"{api}/archives/{key}"))
    if json.loads(body) != {**task, "key": key}:
        raise RuntimeError("Archive metadata did not match the submitted task")
    print("PASS GET /archives/{key} → 200, metadata matches", flush=True)

    body, content_type = expect_status("GET /download/{key}", 200, request(f"{api}/download/{key}"))
    if content_type != "application/zip":
        raise RuntimeError(f"Unexpected download Content-Type: {content_type}")
    with zipfile.ZipFile(io.BytesIO(body)) as downloaded:
        if downloaded.namelist() != [task["name"]] or downloaded.read(task["name"]) != expected_file:
            raise RuntimeError("ZIP contents did not match the original file")
    if output:
        output.write_bytes(body)
    print("PASS GET /download/{key} → 200, ZIP contents match", flush=True)

    expect_status("POST /tasks without url", 400, request(f"{api}/tasks", {"name": "bad.txt"}))
    print("PASS POST /tasks without url → 400", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the deployed archive API.")
    parser.add_argument("api_url", help="HTTPS URL from terraform output -raw api_url")
    parser.add_argument("--source", default="https://www.rfc-editor.org/rfc/rfc9562.txt")
    parser.add_argument("--wait-seconds", type=int, default=180)
    parser.add_argument("--output", type=Path, help="Optional path for the downloaded ZIP")
    args = parser.parse_args()
    smoke(args.api_url.rstrip("/"), args.source, args.wait_seconds, args.output)
