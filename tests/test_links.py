import re

import pytest

from schooltime_core.errors import ValidationError
from schooltime_core.links import LinkPolicy, safe_link


@pytest.fixture
def policies() -> dict[str, LinkPolicy]:
    return {
        "ledger": LinkPolicy("ledger", "Open ledger", "https://portal.example.com", (re.compile(r"/item/[0-9]+"),)),
        "notebook": LinkPolicy("notebook", "Open notebook", "https://notes.example.com:8443", (re.compile(r"/view/[a-z]+"),)),
    }


def test_safe_link_authorizes_only_its_source_and_full_path(policies: dict[str, LinkPolicy]) -> None:
    assert safe_link("ledger", "https://portal.example.com/item/42?token=discard", policies) == {
        "label": "Open ledger",
        "url": "https://portal.example.com/item/42",
    }
    assert safe_link("notebook", "https://portal.example.com/item/42", policies) is None
    assert safe_link("ledger", "https://portal.example.com/item/42/extra", policies) is None


@pytest.mark.parametrize(
    "candidate",
    [
        "http://portal.example.com/item/42",
        "https://portal.example.com.evil.invalid/item/42",
        "https://portal.example.com@evil.invalid/item/42",
        "https://user@portal.example.com/item/42",
        "https://portal.example.com:444/item/42",
        "https://portal.example.com/item/%2f42",
        "https://portal.example.com/item/../42",
        "https://portal.example.com/item/42#fragment",
        "https://[::1]/item/42",
        "https://portal.example.com/item/42\\x00",
        "https://portal.example.com/item/" + "9" * 2100,
    ],
)
def test_unsafe_links_return_none(candidate: str, policies: dict[str, LinkPolicy]) -> None:
    assert safe_link("ledger", candidate, policies) is None


def test_invalid_policy_fails_closed() -> None:
    with pytest.raises(ValidationError):
        LinkPolicy("ledger", "Ledger", "https://PORTAL.example.com", (re.compile("/x"),))
    with pytest.raises(ValidationError):
        LinkPolicy("ledger", "Ledger", "https://portal.example.com/", (re.compile("/x"),))
