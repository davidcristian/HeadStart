import json

import pytest

from app.scrapers.adapters.meta_careers_graphql import (
    extract_lsd_token,
    parse_graphql_json,
    parse_search_response,
)


def test_extract_lsd_token_from_json_blob() -> None:
    html = '{"require":[["LSD",[],{"token":"abc123"}]]}'
    assert extract_lsd_token(html) == "abc123"


def test_extract_lsd_token_from_input_field() -> None:
    html = '<input name="lsd" value="input_token">'
    assert extract_lsd_token(html) == "input_token"


def test_extract_lsd_token_skips_whitespace_json_token_then_input() -> None:
    # The JSON pattern matches a whitespace-only token that strips to empty,
    # so the loop continues to the input-field pattern.
    html = '"LSD",[],{"token":"   "} <input name="lsd" value="fallback">'
    assert extract_lsd_token(html) == "fallback"


def test_extract_lsd_token_missing_raises() -> None:
    with pytest.raises(ValueError, match="missing an lsd token"):
        extract_lsd_token("<html>no token here</html>")


def test_extract_lsd_token_all_matches_whitespace_raises() -> None:
    # Both patterns match but produce whitespace-only tokens -> exhausts the loop.
    html = '"LSD",[],{"token":" "} <input name="lsd" value="  ">'
    with pytest.raises(ValueError, match="missing an lsd token"):
        extract_lsd_token(html)


def test_parse_search_response_rejects_non_dict() -> None:
    with pytest.raises(ValueError, match="expected object"):
        parse_search_response([], company="Meta")


def test_parse_search_response_missing_data_uses_error_message() -> None:
    payload = {"errors": [{"message": "boom"}]}
    with pytest.raises(ValueError, match="GraphQL error: boom"):
        parse_search_response(payload, company="Meta")


def test_parse_search_response_missing_data_no_errors() -> None:
    with pytest.raises(ValueError, match="returned no data"):
        parse_search_response({"data": None}, company="Meta")


def test_parse_search_response_rejects_non_dict_search() -> None:
    payload = {"data": {"job_search_with_featured_jobs": []}}
    with pytest.raises(ValueError, match="unexpected job search payload"):
        parse_search_response(payload, company="Meta")


def test_parse_search_response_rejects_non_list_jobs() -> None:
    payload = {"data": {"job_search_with_featured_jobs": {"all_jobs": {}}}}
    with pytest.raises(ValueError, match="unexpected all_jobs field"):
        parse_search_response(payload, company="Meta")


def test_parse_search_response_skips_non_dict_jobs() -> None:
    payload = {
        "data": {
            "job_search_with_featured_jobs": {
                "all_jobs": [
                    "not-a-dict",
                    {"id": "1", "title": "Engineer", "locations": ["Remote"]},
                ]
            }
        }
    }
    postings = parse_search_response(payload, company="Meta")
    assert len(postings) == 1
    assert postings[0].external_id == "1"
    assert postings[0].location == "Remote"


def test_parse_graphql_json_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_graphql_json("not json", company="Meta")


def test_parse_graphql_json_valid() -> None:
    body = json.dumps(
        {
            "data": {
                "job_search_with_featured_jobs": {
                    "all_jobs": [{"id": "9", "title": "Dev", "locations": []}]
                }
            }
        }
    )
    postings = parse_graphql_json(body, company="Meta")
    assert postings[0].external_id == "9"


def test_first_graphql_error_variants() -> None:
    # errors present but not a list -> falls through to "returned no data".
    with pytest.raises(ValueError, match="returned no data"):
        parse_search_response({"data": None, "errors": "boom"}, company="Meta")

    # errors is a list but first is not a dict -> generic errors message.
    with pytest.raises(ValueError, match="returned errors"):
        parse_search_response({"data": None, "errors": ["oops"]}, company="Meta")

    # errors first entry is a dict with blank message -> generic errors message.
    with pytest.raises(ValueError, match="returned errors"):
        parse_search_response({"data": None, "errors": [{"message": "   "}]}, company="Meta")


def test_to_posting_missing_id_raises() -> None:
    payload = {"data": {"job_search_with_featured_jobs": {"all_jobs": [{"title": "No id"}]}}}
    with pytest.raises(ValueError, match="missing id"):
        parse_search_response(payload, company="Meta")


def test_format_locations_non_list_returns_empty() -> None:
    payload = {
        "data": {
            "job_search_with_featured_jobs": {
                "all_jobs": [{"id": "5", "title": "T", "locations": "not-a-list"}]
            }
        }
    }
    postings = parse_search_response(payload, company="Meta")
    assert postings[0].location == ""
