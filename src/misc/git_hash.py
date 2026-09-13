from src.buildinfo.buildinfo import get_commit


def get_git_hash() -> str:
    return get_commit()
