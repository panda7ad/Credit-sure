from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent
RAW=ROOT/'data'/'raw'; PROCESSED=ROOT/'data'/'processed'; MODELS=ROOT/'models'; REPORTS=ROOT/'reports'
if os.getenv('APP_ENV', 'development') != 'production':
 for p in (RAW,PROCESSED,MODELS,REPORTS): p.mkdir(parents=True,exist_ok=True)
RANDOM_STATE=42
TARGET='TARGET'
