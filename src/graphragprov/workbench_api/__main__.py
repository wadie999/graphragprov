"""Run the workbench API and built frontend."""

import uvicorn

from graphragprov.workbench_api.config import load_config


def main() -> None:
    config = load_config()
    uvicorn.run(
        "graphragprov.workbench_api.app:app", host=config.host, port=config.port, reload=False
    )


if __name__ == "__main__":
    main()
