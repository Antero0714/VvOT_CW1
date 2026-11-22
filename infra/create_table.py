"""Create the Document API table during Terraform apply."""

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def document_request(action, payload):
    token = os.environ["YC_TOKEN"]
    request = Request(
        os.environ["DOCUMENT_API"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-amz-json-1.0",
            "X-Amz-Target": f"DynamoDB_20120810.{action}",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def error_name(error):
    with error:
        try:
            body = json.load(error)
        except ValueError:
            return ""
    if isinstance(body, dict):
        return str(body.get("__type", "")).rsplit("#", 1)[-1]
    return ""


def ensure_table(table_name, key_attribute):
    definition = {
        "TableName": table_name,
        "BillingMode": "PAY_PER_REQUEST",
        "KeySchema": [{"AttributeName": key_attribute, "KeyType": "HASH"}],
        "AttributeDefinitions": [{"AttributeName": key_attribute, "AttributeType": "S"}],
    }
    create_needed = True
    last_result = "table is still being created"
    for attempt in range(15):
        action = "CreateTable" if create_needed else "DescribeTable"
        try:
            if create_needed:
                document_request(action, definition)
                create_needed = False
                action = "DescribeTable"
            table = document_request(action, {"TableName": table_name})["Table"]
        except HTTPError as error:
            kind = error_name(error)
            last_result = f"{action}: HTTP {error.code} {kind}".strip()
            if action == "CreateTable" and kind == "ResourceInUseException":
                create_needed = False
            elif error.code not in {429, 500, 502, 503, 504} and kind not in {
                "ResourceNotFoundException",
                "ThrottlingException",
                "LimitExceededException",
            }:
                raise RuntimeError(last_result) from None
        except (URLError, TimeoutError) as error:
            last_result = f"{action}: {error}"
        else:
            if table["TableStatus"] == "ACTIVE":
                if (
                    table["KeySchema"] != definition["KeySchema"]
                    or definition["AttributeDefinitions"][0] not in table["AttributeDefinitions"]
                ):
                    raise RuntimeError(f"Document table {table_name} has an unexpected key schema")
                print(f"YDB document table {table_name}: ACTIVE", flush=True)
                return
            last_result = f"{action}: {table['TableStatus']}"

        if attempt < 14:
            time.sleep(4)
    raise RuntimeError(f"Document table {table_name} did not become active: {last_result}")


if __name__ == "__main__":
    ensure_table(os.environ["TABLE_NAME"], os.environ["KEY_ATTRIBUTE"])
