from app.main import main


def test_main_has_routes() -> None:
    result = main()
    assert "routes" in result
