"""OpenAPI (YAML/JSON) -> list of text items (plan section 4.1).

Corpus of domain: ``description``, ``summary``, ``title``.
Separate corpora: ``operationId`` (split into words), property and parameter names.
Ignored: paths, enums, examples, formats, ``$ref``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterator

import yaml

try:  # the C loader is much faster on multi-MB specs
    _Loader = yaml.CSafeLoader
except AttributeError:  # pragma: no cover
    _Loader = yaml.SafeLoader

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
TEXT_KEYS = {"description", "summary", "title"}
SKIP_KEYS = {"example", "examples", "x-examples", "enum", "default", "const",
             "pattern", "format", "$ref", "externalDocs", "required"}
SKIP_TOP = {"openapi", "swagger", "servers", "host", "basePath", "schemes",
            "consumes", "produces", "security"}
DOMAIN_KINDS = ("description", "summary", "title")
MAX_DEPTH = 200


@dataclass(frozen=True)
class TextItem:
    text: str
    kind: str      # description | summary | title | operationId | property | parameter
    context: str   # "GET /tokens", "schemas:Token", "info", ...


def load_spec(data: bytes | str) -> dict:
    """Parse an OpenAPI/Swagger document given as YAML or JSON."""
    if isinstance(data, bytes):
        data = data.decode("utf-8-sig")
    stripped = data.lstrip()
    try:
        spec = json.loads(data) if stripped[:1] in "{[" else yaml.load(data, Loader=_Loader)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Could not parse spec: {exc.__class__.__name__}") from exc
    if not isinstance(spec, dict) or not ({"openapi", "swagger", "paths", "components"} & spec.keys()):
        raise ValueError("Input does not look like an OpenAPI/Swagger document")
    return spec


def iter_items(spec: dict) -> Iterator[TextItem]:
    """Yield every text item of the spec, tagged with its context."""
    for key, val in spec.items():
        if key in SKIP_TOP:
            continue
        if key == "paths" and isinstance(val, dict):
            yield from _paths(val)
        elif key == "components" and isinstance(val, dict):
            for section, objs in val.items():
                if isinstance(objs, dict):
                    for name, obj in objs.items():
                        yield from _walk(obj, f"{section}:{name}", 0)
        elif key in ("definitions", "parameters", "responses") and isinstance(val, dict):
            section = "schemas" if key == "definitions" else key
            for name, obj in val.items():
                yield from _walk(obj, f"{section}:{name}", 0)
        else:
            yield from _walk({key: val}, key if key == "info" else "other", 0)


def _paths(paths: dict) -> Iterator[TextItem]:
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for k, v in item.items():
            if isinstance(k, str) and k.lower() in HTTP_METHODS:
                yield from _walk(v, f"{k.upper()} {path}", 0)
            elif k in TEXT_KEYS or k == "parameters":
                yield from _walk({k: v}, f"PATH {path}", 0)


def _walk(node: Any, ctx: str, depth: int) -> Iterator[TextItem]:
    if depth > MAX_DEPTH:
        return
    if isinstance(node, list):
        for x in node:
            yield from _walk(x, ctx, depth + 1)
        return
    if not isinstance(node, dict):
        return
    if isinstance(node.get("name"), str) and isinstance(node.get("in"), str):
        yield TextItem(node["name"], "parameter", ctx)
    for k, v in node.items():
        if not isinstance(k, str) or k in SKIP_KEYS:
            continue
        if k in TEXT_KEYS and isinstance(v, str):
            yield TextItem(v, k, ctx)
        elif k == "operationId" and isinstance(v, str):
            yield TextItem(v, "operationId", ctx)
        elif k == "properties" and isinstance(v, dict):
            for name, sub in v.items():
                if isinstance(name, str):
                    yield TextItem(name, "property", ctx)
                yield from _walk(sub, ctx, depth + 1)
        else:
            yield from _walk(v, ctx, depth + 1)


def extract(data: bytes | str) -> list[TextItem]:
    return list(iter_items(load_spec(data)))
