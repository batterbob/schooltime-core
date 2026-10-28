from schooltime_core.errors import ValidationError
from schooltime_core.providers import SourceSpec
from schooltime_core.schema import require_source_id, require_timezone


def test_source_specs_are_bounded_and_generic() -> None:
    source = SourceSpec("ledger", "Ledger", frozenset({"grades"}))
    assert source.source_id == "ledger"


def test_source_id_and_timezone_fail_closed() -> None:
    for value in ("Upper", "two words", "", "x" * 33):
        try:
            require_source_id(value)
        except ValidationError:
            pass
        else:
            raise AssertionError(value)
    assert require_timezone("America/New_York") == "America/New_York"
