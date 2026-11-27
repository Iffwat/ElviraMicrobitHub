import os

# Run Qt without a display (also set in CI). Must happen before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
