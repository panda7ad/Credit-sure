"""Download Home Credit Default Risk via Kaggle CLI.
Prereq: accept competition rules and configure Kaggle credentials.
"""
import subprocess, zipfile
from config import RAW
archive=RAW/'home-credit-default-risk.zip'
subprocess.run(['kaggle','competitions','download','-c','home-credit-default-risk','-p',str(RAW)],check=True)
with zipfile.ZipFile(archive) as z: z.extractall(RAW)
print('Extracted to', RAW)
