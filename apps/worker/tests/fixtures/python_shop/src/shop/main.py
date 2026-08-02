from fastapi import FastAPI

from .services.orders import create_order


def create_app() -> FastAPI:
    app = FastAPI()

    @app.post("/orders")
    async def submit_order(total: str) -> dict[str, str]:
        return create_order(total)

    return app


def main() -> None:
    create_app()


if __name__ == "__main__":
    main()
