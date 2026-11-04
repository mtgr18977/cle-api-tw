import pytest

from apiterm.clean import clean_text, deduplicate, split_identifier
from apiterm.extract import TextItem, extract, load_spec


def kinds(items, k):
    return [i.text for i in items if i.kind == k]


def test_extract_kinds_and_contexts(sample_spec):
    items = extract(sample_spec)
    assert "createAccessToken" in kinds(items, "operationId")
    assert "token_type" in kinds(items, "property")
    assert "client_id" in kinds(items, "parameter")
    op = next(i for i in items if i.kind == "summary" and i.text == "Create an access token")
    assert op.context == "POST /tokens"
    assert any(i.context == "schemas:AccessToken" and i.kind == "title" for i in items)


def test_extract_ignores_examples_enums_paths(sample_spec):
    texts = {i.text for i in extract(sample_spec)}
    assert "abc_123" not in texts and "read" not in texts and "/tokens" not in texts


def test_property_named_description_is_not_text():
    spec = """openapi: 3.0.0
paths: {}
components:
  schemas:
    X:
      properties:
        description: {type: string, description: The free text description.}
"""
    items = extract(spec)
    assert kinds(items, "property") == ["description"]
    assert kinds(items, "description") == ["The free text description."]


def test_json_input_and_bad_input():
    assert extract('{"openapi":"3.0.0","info":{"title":"A b"},"paths":{}}')[0].text == "A b"
    with pytest.raises(ValueError):
        load_spec("just: some yaml")
    with pytest.raises(ValueError):
        load_spec("{ not json")


def test_clean_text_markdown_and_literals():
    raw = ("Use **bold** and `access_token` or `{\"a\": 1}`.\n\n```py\nprint(1)\n```\n"
           "See [the docs](https://x.io/a) at https://x.io. Value \"abc_123\" is <b>ignored</b>.\n"
           "- first item\n- second item\nwrapped\nline")
    out = clean_text(raw)
    assert "access_token" in out and "`" not in out and "print" not in out
    assert "x.io" not in out and "abc_123" not in out and "<b>" not in out and "**" not in out
    assert "the docs" in out
    assert "first item. second item. wrapped line." in out


@pytest.mark.parametrize("name,expected", [
    ("createAccessToken", ["create", "access", "token"]),
    ("create_access_token", ["create", "access", "token"]),
    ("GetAPIKeys", ["get", "API", "keys"]),
    ("list-v1-webhooks", ["list", "webhooks"]),
])
def test_split_identifier(name, expected):
    assert split_identifier(name) == expected


def test_deduplicate_counts_and_contexts():
    items = [TextItem("The   token expires.", "description", "GET /a"),
             TextItem("the token expires.", "description", "GET /b"),
             TextItem("Another one.", "summary", "GET /a"),
             TextItem("createToken", "operationId", "GET /a"),   # not a domain kind
             TextItem("```code```", "description", "GET /c")]    # empty after cleaning
    uniq, st = deduplicate(items)
    assert (st.items_before, st.items_after, st.removed) == (3, 2, 1)
    first = uniq[0]
    assert first.n_raw == 2 and first.contexts == {"GET /a", "GET /b"}
