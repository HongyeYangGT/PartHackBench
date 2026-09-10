                                                    
from __future__ import annotations
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
cmds=[[sys.executable,str(ROOT/'scripts'/'verify_release_integrity.py')],[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v']]
for cmd in cmds:
    rc=subprocess.call(cmd,cwd=ROOT)
    if rc: raise SystemExit(rc)
print('PartHackBench package verification: OK')
