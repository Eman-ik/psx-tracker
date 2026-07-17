"""Keep the test suite deterministic and independent of a developer's .env."""

import os


# Set this before test modules import live_api.app.main, whose application
# settings and provider are initialized at module import time.
os.environ["PROVIDER"] = "mock"
