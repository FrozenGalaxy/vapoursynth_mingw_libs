#!/usr/bin/env python3

import os
import sys
import re

if len(sys.argv) > 1 and sys.argv[1] in ("install", "uninstall"):
    mode = sys.argv.pop(1)
else:
    mode = "install"

_DEBUG = False

def run(cmd):
    if _DEBUG:
        print(f"\n-- {os.getcwd()} :: {cmd}\n--")
    if os.system(cmd) != 0:
        print(f"FAILED: {cmd}")
        sys.exit(1)

def need_args(n):
    if len(sys.argv) != n:
        print("usage: script.py <arch:64/32> <version:R74> <prefix> <dlltool> <gendef> <pyver>")
        sys.exit(1)

VS_PC = """prefix=%%PREFIX%%
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include/vapoursynth

Name: vapoursynth
Description: A frameserver for the 21st century
Version: %%VERSION%%

Requires.private: zimg
Libs: -L${libdir} -lvapoursynth
Libs.private: -L${libdir} -lzimg
Cflags: -I${includedir}
"""

VSS_PC = """prefix=%%PREFIX%%
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
includedir=${prefix}/include/vapoursynth

Name: vapoursynth-script
Description: Library for interfacing VapourSynth with Python
Version: %%VERSION%%

Requires: vapoursynth
Requires.private: python-%%PY_DOT%%
Libs: -L${libdir} -lvapoursynth-script
Libs.private: -lpython%%PY%%
Cflags: -I${includedir}
"""

# -----------------------------

need_args(7)

arch     = sys.argv[1]
ver      = sys.argv[2]       # e.g. R74
prefix   = sys.argv[3]
dlltool  = sys.argv[4]
gendef   = sys.argv[5]
pyver    = sys.argv[6]       # e.g. 3.12

ver_num = ver[1:]            # "74"
py_nodot = pyver.replace(".", "")

zip_name = f"VapourSynth{arch}-Portable-{ver}.zip"
url = f"https://github.com/vapoursynth/vapoursynth/releases/download/{ver}/{zip_name}"

# -----------------------------
# workspace
# -----------------------------

run("rm -rf work out")
run("mkdir -p work out")

os.chdir("work")

# -----------------------------
# download + extract
# -----------------------------

print("Downloading release...")
run(f"wget {url}")

print("Extracting release zip...")
run(f'7z x -aoa -snl "{zip_name}"')

# -----------------------------
# extract wheel
# -----------------------------

print("Locating wheel...")

wheel_path = None

for root, dirs, files in os.walk("."):
    for f in files:
        if f.lower().endswith(".whl"):
            wheel_path = os.path.join(root, f)
            break
    if wheel_path:
        break

if not wheel_path:
    print("Wheel not found!")
    sys.exit(1)

print(f"Using wheel: {wheel_path}")

run(f'7z x -aoa "{wheel_path}" -owheel_extract')

vs = "wheel_extract/vapoursynth"

# -----------------------------
# binaries
# -----------------------------

print("Copying DLLs...")
run(f"mkdir -p ../out/bin")
run(f"cp {vs}/vsscript.dll ../out/bin/")
run(f"cp {vs}/libvapoursynth.dll ../out/bin/")

# -----------------------------
# import libs (.a)
# -----------------------------

print("Generating import libraries...")

# vapoursynth
run(f"{gendef} {vs}/libvapoursynth.dll")
run(f"{dlltool} -m i386:x86-64 -D libvapoursynth.dll -d libvapoursynth.def -l libvapoursynth.a")

# vsscript
run(f"{gendef} {vs}/vsscript.dll")
run(f"{dlltool} -m i386:x86-64 -D vsscript.dll -d vsscript.def -l libvapoursynth-script.a")

run("mkdir -p ../out/lib")
run("mv libvapoursynth.a ../out/lib/")
run("mv libvapoursynth-script.a ../out/lib/")

# -----------------------------
# headers
# -----------------------------

print("Copying headers...")
run("mkdir -p ../out/include")
run(f"cp -r {vs}/include ../out/include/vapoursynth")

# -----------------------------
# pkg-config
# -----------------------------

print("Generating pkg-config files...")

run("mkdir -p ../out/lib/pkgconfig")

pc_vs = VS_PC.replace("%%PREFIX%%", prefix).replace("%%VERSION%%", ver_num)

pc_vss = VSS_PC \
    .replace("%%PREFIX%%", prefix) \
    .replace("%%VERSION%%", ver_num) \
    .replace("%%PY_DOT%%", pyver) \
    .replace("%%PY%%", py_nodot)

with open("../out/lib/pkgconfig/vapoursynth.pc", "w") as f:
    f.write(pc_vs)

with open("../out/lib/pkgconfig/vapoursynth-script.pc", "w") as f:
    f.write(pc_vss)

# -----------------------------
# install
# -----------------------------

os.chdir("..")

print(f"Installing to {prefix} ...")
run(f"mkdir -p {prefix}")
run(f"rsync -a out/ {prefix}/")

print("Done.")
