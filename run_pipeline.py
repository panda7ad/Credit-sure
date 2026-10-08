import subprocess,sys
for mod in ['src.build_dataset','src.eda','src.train']:
 print('\n>>>',mod); subprocess.run([sys.executable,'-m',mod],check=True)
