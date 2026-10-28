def test_package_import_is_side_effect_free() -> None:
    import schooltime_core

    assert schooltime_core.__version__ == "0.1.0"
