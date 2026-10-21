"""Tests verifying that all required dependencies are installed and importable in ml_service.

Required libraries to verify:
- prophet
- torch (CPU)
- statsmodels
- pandas
- scikit-learn
- fastapi
- uvicorn
- SQLAlchemy
- psycopg
- apscheduler
- pyarrow
- holidays
"""

import sys
import pytest


def test_python_version_is_3_12():
    """Verify that ml_service venv is running Python 3.12."""
    assert sys.version_info.major == 3
    assert sys.version_info.minor == 12, f"Expected Python 3.12, got {sys.version}"


def test_import_prophet():
    """Verify prophet can be imported and instantiated."""
    import prophet
    assert hasattr(prophet, "__version__")
    assert prophet.Prophet is not None


def test_import_torch_cpu():
    """Verify torch is importable in CPU mode."""
    import torch
    assert hasattr(torch, "__version__")
    # Verify CPU build
    t = torch.tensor([1.0, 2.0, 3.0])
    assert t.device.type == "cpu"
    assert t.sum().item() == 6.0


def test_import_statsmodels():
    """Verify statsmodels is importable."""
    import statsmodels
    assert hasattr(statsmodels, "__version__")


def test_import_pandas():
    """Verify pandas is importable."""
    import pandas as pd
    assert hasattr(pd, "__version__")


def test_import_scikit_learn():
    """Verify scikit-learn is importable."""
    import sklearn
    assert hasattr(sklearn, "__version__")


def test_import_fastapi():
    """Verify fastapi is importable."""
    import fastapi
    assert hasattr(fastapi, "__version__")
    assert hasattr(fastapi, "FastAPI")


def test_import_uvicorn():
    """Verify uvicorn is importable."""
    import uvicorn
    assert hasattr(uvicorn, "__version__")


def test_import_sqlalchemy():
    """Verify SQLAlchemy is importable."""
    import sqlalchemy
    assert hasattr(sqlalchemy, "__version__")


def test_import_psycopg():
    """Verify psycopg (v3) is importable."""
    import psycopg
    assert hasattr(psycopg, "__version__")


def test_import_apscheduler():
    """Verify apscheduler is importable."""
    import apscheduler
    assert hasattr(apscheduler, "__version__")


def test_import_pyarrow():
    """Verify pyarrow is importable."""
    import pyarrow
    assert hasattr(pyarrow, "__version__")


def test_import_holidays():
    """Verify holidays package is importable."""
    import holidays
    assert hasattr(holidays, "__version__")
    in_holidays = holidays.India()
    assert in_holidays is not None
