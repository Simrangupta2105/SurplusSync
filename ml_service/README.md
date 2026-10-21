# SurplusSync ML Service (`ml_service/`)

Independent Python package for SurplusSync Module 2 (AI/ML Forecasting, Waste Risk Scoring, and Reorder Recommendation Engine).

---

## 1. Environment & Compatibility Rationale

The primary SurplusSync backend operates on **Python 3.14**. However, statistical, forecasting, and deep-learning packages (specifically **Prophet**, **PyTorch CPU**, **Statsmodels**, and underlying numerical dependencies like NumPy and SciPy) lack stable pre-compiled wheels for Python 3.14 on Windows (`win_amd64`).

### Compatibility Matrix on Windows (`win_amd64`):

| Package | Tested Version | Python 3.12 | Python 3.13 | Python 3.14 | Compatibility Status |
|:---|:---|:---:|:---:|:---:|:---|
| **prophet** | 1.5.0 | Yes | No | No | Windows wheel available; C++ Stan compiler backend requires stable 3.12 |
| **torch (CPU)** | 2.14.1+cpu | Yes | Yes | No | Official CPU wheel on PyTorch index |
| **statsmodels** | 0.15.0 | Yes | Yes | No | Precompiled C extensions available |
| **pandas** | 3.0.6 | Yes | Yes | Yes | C/Cython extensions available |
| **scikit-learn** | 1.9.1 | Yes | Yes | Yes | C/Cython extensions available |
| **fastapi** | 0.156.2 | Yes | Yes | Yes | Pure Python / anyio |
| **uvicorn** | 0.54.0 | Yes | Yes | Yes | Pure Python / click / h11 |
| **SQLAlchemy** | 2.1.5 | Yes | Yes | Yes | C-extensions with fallback |
| **psycopg** | 3.3.6 | Yes | Yes | Yes | Binary wheel `psycopg[binary]` |
| **apscheduler** | 3.11.3 | Yes | Yes | Yes | Pure Python |
| **pyarrow** | 26.0.0 | Yes | Yes | Yes | Arrow C++ bindings |

**Selected Runtime:** **Python 3.12 (64-bit)** is the newest Python release that simultaneously and reliably supports all required machine-learning, time-series, and database packages on Windows.

---

## 2. Virtual Environment Setup on Windows

`ml_service` maintains its own dedicated virtual environment (`ml_service/venv`), completely isolated from `backend/` and the root `venv/`.

### Creating the Virtual Environment

From the project root (`c:\Users\...\SurplusSync`):

```powershell
# Using the Windows Python Launcher to target Python 3.12
py -3.12 -m venv ml_service/venv
```

### Activating the Environment on Windows

**In PowerShell:**
```powershell
.\ml_service\venv\Scripts\Activate.ps1
```
*(If execution policy blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the current shell session).*

**In Command Prompt (cmd.exe):**
```cmd
ml_service\venv\Scripts\activate.bat
```

### Installing Dependencies

```powershell
# 1. Install PyTorch CPU directly from PyTorch index (prevents heavy CUDA download)
.\ml_service\venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu

# 2. Install pinned dependencies from requirements.txt
.\ml_service\venv\Scripts\pip install -r ml_service/requirements.txt
```

---

## 3. Verifying Package Imports

Run the verification one-liner:
```powershell
.\ml_service\venv\Scripts\python -c "import prophet, torch, statsmodels, pandas, sklearn, fastapi, uvicorn, sqlalchemy, psycopg, apscheduler, pyarrow; print('All core ML packages imported successfully!')"
```

---

## 4. Running Tests

To run the test suite using pytest inside the `ml_service` environment:

```powershell
.\ml_service\venv\Scripts\pytest ml_service/tests -v
```

---

## 5. Directory Layout

```
ml_service/
├── app/                  # FastAPI service (Task 7)
├── config/               # Configuration YAMLs (scoring.yaml, calibration.yaml)
├── data/
│   ├── raw/              # Benchmark datasets (gitignored)
│   ├── builder.py        # Django ledger dataset builder (Task 1)
│   └── food_waste.py     # Benchmark dataset cleaner & loaders (Task 1)
├── docs/                 # ML evaluations & documentation
├── models/               # Forecasting & ML models (Prophet, LSTM, HistGB)
├── scoring/              # Risk scorer and Reorder engine (Tasks 5 & 6)
├── sql/                  # PostgreSQL roles & schemas (create_roles.sql)
├── tests/                # Test suites & invariants
├── requirements.txt      # Pinned dependency manifest
└── README.md             # This guide
```
