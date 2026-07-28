""" Backward-compatible shim — prefer `modules.bi_data.mock`. """
from modules.bi_data.mock import *  # noqa: F401,F403

if __name__ == "__main__":
    from modules.bi_data.mock import build_database

    build_database(1000)
