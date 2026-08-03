import json

from .service import Service


def main():
    return json.dumps({"service": Service().name})


if __name__ == "__main__":
    main()
