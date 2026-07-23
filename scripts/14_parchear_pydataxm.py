import argparse, importlib.metadata, py_compile
from pathlib import Path

p=argparse.ArgumentParser(); p.add_argument("--apply",action="store_true"); a=p.parse_args()
v=importlib.metadata.version("pydataxm")
if v!="0.3.17": raise RuntimeError(f"pydataxm {v} no soportado")
r=Path(importlib.metadata.distribution("pydataxm").locate_file(""))
f=r/"pydataxm"/"pydataxm.py"
old,new=b"freq='M'",b"freq='ME'"
raw=f.read_bytes(); co,cn=raw.count(old),raw.count(new)
print("Archivo:",f); print("freq='M':",co); print("freq='ME':",cn)
if co==0 and cn==1:
    py_compile.compile(str(f),doraise=True); print("Estado: PARCHE YA APLICADO"); raise SystemExit(0)
if co!=1 or cn!=0: raise RuntimeError("Estructura inesperada; no se modifico el paquete")
if not a.apply: print("Estado: PARCHE PENDIENTE; ejecute con --apply"); raise SystemExit(2)
for i in range(1,1000):
    b=f.with_name(f"{f.name}.bak_v{i:03d}")
    if not b.exists(): break
b.write_bytes(raw); f.write_bytes(raw.replace(old,new,1)); saved=f.read_bytes()
if saved.count(old)!=0 or saved.count(new)!=1 or b.read_bytes()!=raw:
    f.write_bytes(raw); raise RuntimeError("Validacion fallida; se restauro el original")
py_compile.compile(str(f),doraise=True)
print("Respaldo:",b); print("Estado: PARCHE APLICADO CORRECTAMENTE")
