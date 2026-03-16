from app.services import load_settings


def build_routes() -> dict[str, object]:
    settings = load_settings()
    return {
        "health": "/health",
        "environment": settings["environment"],
    }
