#!/usr/bin/env python3
"""
Utility script to convert the project's OpenAPI specification into a Postman collection.
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


class PostmanConverter:
    def __init__(self, spec: Dict[str, Any]) -> None:
        self.spec = spec
        self.components = spec.get("components", {})

    def build_collection(self) -> Dict[str, Any]:
        base_url = self._get_base_url()
        info = self.spec.get("info", {})

        collection: Dict[str, Any] = {
            "info": {
                "name": info.get("title", "API Collection"),
                "description": info.get("description", ""),
                "_postman_id": str(uuid.uuid4()),
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": [],
            "variable": [
                {"key": "baseUrl", "value": base_url},
                {"key": "accessToken", "value": "<paste-access-token>"},
            ],
            "auth": {
                "type": "bearer",
                "bearer": [
                    {"key": "token", "value": "{{accessToken}}", "type": "string"},
                ],
            },
        }

        folders: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

        paths = self.spec.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                method_lower = method.lower()
                if method_lower not in HTTP_METHODS:
                    continue
                if not isinstance(operation, dict):
                    continue

                request_item = self._build_request_item(
                    path=path,
                    method=method_lower,
                    path_item=path_item,
                    operation=operation,
                )

                tags = operation.get("tags") or ["General"]
                primary_tag = tags[0]
                folder = folders.setdefault(primary_tag, {"name": primary_tag, "item": []})
                folder["item"].append(request_item)

        collection["item"] = list(folders.values())
        return collection

    def _build_request_item(
        self,
        path: str,
        method: str,
        path_item: Dict[str, Any],
        operation: Dict[str, Any],
    ) -> Dict[str, Any]:
        display_name = (
            operation.get("summary")
            or operation.get("operationId")
            or f"{method.upper()} {path}"
        )

        url, header_params = self._build_url(path, path_item, operation)

        request: Dict[str, Any] = {
            "method": method.upper(),
            "header": [],
            "url": url,
        }

        description = operation.get("description")
        if description:
            request["description"] = description

        self._apply_security(operation, request)

        headers = request["header"]
        header_keys = set()
        headers.append({"key": "Accept", "value": "application/json"})
        header_keys.add("accept")

        for header_entry in header_params:
            header_key_lower = header_entry["key"].lower()
            if header_key_lower not in header_keys:
                headers.append(header_entry)
                header_keys.add(header_key_lower)

        body = self._build_body(operation)
        if body is not None:
            request["body"] = body
            if "content-type" not in header_keys:
                headers.append({"key": "Content-Type", "value": "application/json"})
                header_keys.add("content-type")

        item = {
            "name": display_name,
            "request": request,
            "response": [],
        }
        return item

    def _get_base_url(self) -> str:
        servers = self.spec.get("servers")
        if servers:
            url = servers[0].get("url", "").strip()
            if url:
                return url.rstrip("/")
        return "http://localhost:8000"

    def _apply_security(self, operation: Dict[str, Any], request: Dict[str, Any]) -> None:
        security = operation.get("security", self.spec.get("security"))
        if not security:
            request["auth"] = {"type": "noauth"}
            return

        for requirement in security:
            if not requirement:
                request["auth"] = {"type": "noauth"}
                return

    def _collect_parameters(
        self,
        path_item: Dict[str, Any],
        operation: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        combined: Dict[Tuple[str, str], Dict[str, Any]] = OrderedDict()

        for source in (path_item.get("parameters", []), operation.get("parameters", [])):
            for param in source:
                resolved = self._resolve_ref(param)
                if not isinstance(resolved, dict):
                    continue
                name = resolved.get("name")
                location = resolved.get("in")
                if not name or not location:
                    continue
                combined[(name, location)] = resolved
        return list(combined.values())

    def _build_url(
        self,
        path: str,
        path_item: Dict[str, Any],
        operation: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        parameters = self._collect_parameters(path_item, operation)
        path_params = [p for p in parameters if p.get("in") == "path"]
        query_params = [p for p in parameters if p.get("in") == "query"]
        header_params = [p for p in parameters if p.get("in") == "header"]

        raw_path = self._convert_path_variables(path)
        url: Dict[str, Any] = {
            "raw": "{{baseUrl}}" + raw_path,
            "host": ["{{baseUrl}}"],
            "path": self._split_path(raw_path),
        }

        if path_params:
            variables = []
            for param in path_params:
                value = self._parameter_example(param)
                variables.append(
                    {
                        "key": param["name"],
                        "value": value,
                        "description": param.get("description", ""),
                    }
                )
            url["variable"] = variables

        if query_params:
            queries = []
            for param in query_params:
                value = self._parameter_example(param)
                queries.append(
                    {
                        "key": param["name"],
                        "value": value,
                        "description": param.get("description", ""),
                    }
                )
            url["query"] = queries

        if header_params:
            header_entries: List[Dict[str, Any]] = []
            for param in header_params:
                value = self._parameter_example(param)
                header_entries.append(
                    {
                        "key": param["name"],
                        "value": value,
                        "description": param.get("description", ""),
                    }
                )
        else:
            header_entries = []
        return url, header_entries

    def _parameter_example(self, parameter: Dict[str, Any]) -> str:
        if "example" in parameter:
            example = parameter["example"]
        else:
            schema = parameter.get("schema")
            example = self._schema_example(schema)
        if isinstance(example, (dict, list)):
            return json.dumps(example)
        if example is None:
            return ""
        return str(example)

    def _build_body(self, operation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        request_body = operation.get("requestBody")
        if not request_body:
            return None

        resolved = self._resolve_ref(request_body)
        if not isinstance(resolved, dict):
            return None

        content = resolved.get("content") or {}
        json_content = content.get("application/json")
        if not json_content:
            return None

        schema = json_content.get("schema")
        example = None

        if "examples" in json_content and isinstance(json_content["examples"], dict):
            example_values = list(json_content["examples"].values())
            if example_values:
                example = self._resolve_ref(example_values[0]).get("value")
        if example is None and "example" in json_content:
            example = json_content["example"]
        if example is None:
            example = self._schema_example(schema)

        raw_body = "{}" if example is None else json.dumps(example, indent=2)
        return {
            "mode": "raw",
            "raw": raw_body,
            "options": {"raw": {"language": "json"}},
        }

    def _schema_example(self, schema: Any, depth: int = 0) -> Any:
        schema = self._resolve_schema(schema)
        if not isinstance(schema, dict):
            return schema

        if "example" in schema:
            return schema["example"]
        if "default" in schema:
            return schema["default"]
        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]

        if depth > 4:
            return None

        schema_type = schema.get("type")
        if not schema_type:
            if "properties" in schema:
                schema_type = "object"
            elif "items" in schema:
                schema_type = "array"

        if schema_type == "object":
            properties = schema.get("properties", {})
            example_object: Dict[str, Any] = {}
            for prop_name, prop_schema in properties.items():
                example_value = self._schema_example(prop_schema, depth + 1)
                if example_value is None:
                    example_value = ""
                example_object[prop_name] = example_value
            return example_object

        if schema_type == "array":
            items_schema = schema.get("items")
            example_item = self._schema_example(items_schema, depth + 1)
            return [example_item] if example_item is not None else []

        if schema_type == "boolean":
            return True
        if schema_type == "integer":
            return 0
        if schema_type == "number":
            return 0

        if schema_type == "string":
            fmt = schema.get("format")
            if fmt == "date-time":
                return "2024-01-01T00:00:00Z"
            if fmt == "date":
                return "2024-01-01"
            if fmt == "email":
                return "user@example.com"
            if fmt == "uuid":
                return "00000000-0000-0000-0000-000000000000"
            if fmt == "uri":
                return "https://example.com"
            if fmt == "phone":
                return "+1234567890"
            return "string"

        return None

    def _resolve_schema(self, schema: Any) -> Any:
        schema = self._resolve_ref(schema)
        if not isinstance(schema, dict):
            return schema

        if "allOf" in schema:
            merged: Dict[str, Any] = {}
            for subschema in schema["allOf"]:
                merged = self._merge_schema_dicts(merged, self._resolve_schema(subschema))
            remainder = {k: v for k, v in schema.items() if k != "allOf"}
            schema = self._merge_schema_dicts(merged, remainder)

        if "oneOf" in schema:
            return self._resolve_schema(schema["oneOf"][0])
        if "anyOf" in schema:
            return self._resolve_schema(schema["anyOf"][0])

        return schema

    def _merge_schema_dicts(self, target: Dict[str, Any], source: Any) -> Dict[str, Any]:
        if not isinstance(source, dict):
            return target
        result = copy.deepcopy(target)
        for key, value in source.items():
            if key == "properties":
                result.setdefault("properties", {})
                for prop_name, prop_schema in value.items():
                    result["properties"][prop_name] = prop_schema
            elif key == "required":
                result.setdefault("required", [])
                for required_field in value:
                    if required_field not in result["required"]:
                        result["required"].append(required_field)
            else:
                result[key] = value
        return result

    def _resolve_ref(self, node: Any) -> Any:
        if not isinstance(node, dict) or "$ref" not in node:
            return node

        ref = node["$ref"]
        if not ref.startswith("#/"):
            return node

        parts = ref.lstrip("#/").split("/")
        data: Any = self.spec
        for part in parts:
            if not isinstance(data, dict):
                raise KeyError(f"Cannot resolve reference: {ref}")
            data = data[part]
        if isinstance(data, dict) and "$ref" in data:
            return self._resolve_ref(data)
        return copy.deepcopy(data)

    def _convert_path_variables(self, path: str) -> str:
        return re.sub(r"{([^{}]+)}", lambda match: f"{{{{{match.group(1)}}}}}", path)

    def _split_path(self, raw_path: str) -> List[str]:
        clean = raw_path.lstrip("/")
        if not clean:
            return []
        segments = []
        for segment in clean.split("/"):
            if segment:
                segments.append(segment)
        return segments


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    spec_path = root / "openapi.yaml"
    output_path = root / "postman" / "FakeStore.postman_collection.json"

    with spec_path.open("r", encoding="utf-8") as spec_file:
        spec = yaml.safe_load(spec_file)

    converter = PostmanConverter(spec)
    collection = converter.build_collection()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    print(f"Postman collection written to {output_path}")


if __name__ == "__main__":
    main()
