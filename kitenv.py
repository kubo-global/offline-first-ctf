"""Read the kit's .env, so the scripts and docker compose use the same settings.
What is already set in the environment wins over the file."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def pack():
    """The folder of the challenge pack in use (PACK in .env)."""
    p = os.environ.get("PACK", "./example-pack")
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(HERE, p))
