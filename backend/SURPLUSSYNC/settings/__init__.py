"""
Settings package for SURPLUSSYNC Django project.
Loads the appropriate settings based on the SURPLUSSYNC_ENV environment variable.
"""

import os

# Determine which settings to use
ENV = os.getenv('SURPLUSSYNC_ENV', 'dev').lower()

if ENV == 'prod':
    from .prod import *  # noqa
elif ENV == 'dev':
    from .dev import *  # noqa
else:
    raise ValueError(
        f"Invalid SURPLUSSYNC_ENV '{ENV}'. Must be 'dev' or 'prod'."
    )
