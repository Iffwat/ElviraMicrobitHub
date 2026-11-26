"""PyInstaller entry script (needs absolute imports, unlike __main__.py)."""

from microbithub.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
