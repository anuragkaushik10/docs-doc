from app.routes import build_routes
from app.services import load_settings


def main() -> dict[str, object]:
    return {
        "routes": build_routes(),
        "settings": load_settings(),
    }


if __name__ == "__main__":
    main()
