#!/usr/bin/env python3

import sys
import os
import urllib
import subprocess
import re

_DEBUG = False

def is_tool(name):
    from distutils.spawn import find_executable
    return find_executable(name) is not None

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
Cflags: -I${includedir}"""

VSS_PC = """prefix=%%PREFIX%% 
exec_prefix=${prefix} 
libdir=${exec_prefix}/lib 
includedir=${prefix}/include/vapoursynth 
 
Name: vapoursynth-script 
Description: Library for interfacing VapourSynth with Python 
Version: %%VERSION%%
 
Requires: vapoursynth 
Requires.private: python-%%PY_VER_DOT%%
Libs: -L${libdir} -lvapoursynth-script 
Libs.private: -lpython%%PY_VER%%
Cflags: -I${includedir}"""

def runCmd(cmd):
    if _DEBUG:
        print("\n--Running command in '%s': '%s'\n--" % (os.getcwd(), cmd))
    if os.system(cmd) != 0:
        print("Failed to execute: " + str(cmd))
        exit(1)

def exitHelp():
    print("install_vapoursynth_libs.py install/uninstall <64/32> <version> <install_prefix> <dlltool> <gendef> - e.g install_vapoursynth_libs.py 64 R49 /test/cross_compilers/....../ DLLTOOLPATH GENDEFPATH")
    exit(1)

def simplePatch(infile, replacetext, withtext):
    lines = []
    print("Patching " + infile)
    with open(infile) as f:
        for line in f:
            line = line.replace(replacetext, withtext)
            lines.append(line)
    with open(infile, 'w') as f2:
        for line in lines:
            f2.write(line)

def lib_to_a(lib_filename, a_output_name, dlltool):
    # Extract symbols from the .lib file
    symbols_txt = "symbols.txt"
    with open(symbols_txt, "w") as symbols_file:
        subprocess.run(["llvm-nm", lib_filename], stdout=symbols_file)

    # Parse symbols and create a .def file
    def_filename = "temp.def"
    with open(symbols_txt, "r") as f:
        lines = f.readlines()

    exports = []
    for line in lines:
        match = re.match(r'^[0-9a-fA-F]+\s+([a-zA-Z_][a-zA-Z0-9_]*)$', line)
        if match:
            exports.append(match.group(1))

    with open(def_filename, "w") as f:
        f.write(f"LIBRARY {os.path.splitext(lib_filename)[0]}\n")
        f.write("EXPORTS\n")
        for symbol in exports:
            f.write(f"{symbol}\n")

    # Create the .a file using llvm-dlltool
    subprocess.run([dlltool, "-d", def_filename, "-l", a_output_name])

    # Clean up temporary files
    os.remove(symbols_txt)
    os.remove(def_filename)

    print(f"Created {a_output_name} from {lib_filename}")

def check_version(ver_suff):
    if int(ver_suff) < 58:
        print("Error: VapourSynth version must be 58 or higher.")
        exit(1)

if not is_tool("rsync") or not is_tool("7z"):
    print("Please make sure that p7zip and rsync are installed.")
    exit(1)

if len(sys.argv) != 7:
    exitHelp()
else:
    if sys.argv[1] == "install":
        arch     = sys.argv[2]
        ver      = sys.argv[3]
        ver_suff = ver[1:]
        prefix   = sys.argv[4]
        dlltool  = sys.argv[5]
        gendef   = sys.argv[6]

        check_version(ver_suff)

        runCmd("mkdir -p work")
        runCmd("mkdir -p bin")
        os.chdir("work")
        print("Downloading")
        runCmd("wget https://github.com/vapoursynth/vapoursynth/releases/download/{0}/VapourSynth{1}-Portable-{0}.zip".format(ver, arch))
        runCmd('7z x -aoa "VapourSynth{1}-Portable-{0}.zip"'.format(ver, arch))

        print("Local installing binaries")
        runCmd("cp {0} ../bin".format("VSScript.dll"))

        VSS_PC = VSS_PC.replace("%%PY_VER_DOT%%", "3.12").replace("%%PY_VER%%", "312")

        print("Creating library")

        # Convert VapourSynth.lib to libvapoursynth.a
        lib_to_a("sdk/lib64/VapourSynth.lib", "libvapoursynth.a", dlltool)

        # Create libvapoursynth-script.a from VSScript.dll
        runCmd("{0} {1}".format(gendef, "VSScript.dll"))
        runCmd(f"{dlltool} -m i386:x86-64 -D VSScript.dll -d VSScript.def -l libvapoursynth-script.a")

        runCmd("mkdir lib")

        runCmd("mv libvapoursynth.a lib/")
        runCmd("mv libvapoursynth-script.a lib/")

        os.chdir("lib")

        runCmd("mkdir pkgconfig")

        os.chdir("pkgconfig")

        print("Creating pkgconfig")

        pc_script = VSS_PC.replace('%%PREFIX%%', prefix).replace('%%VERSION%%', ver_suff)
        pc        = VS_PC.replace('%%PREFIX%%', prefix).replace('%%VERSION%%', ver_suff)

        with open("vapoursynth.pc", "w") as f:
            f.write(pc)

        with open("vapoursynth-script.pc", "w") as f:
            f.write(pc_script)

        os.chdir("..")
        os.chdir("..")

        runCmd("mkdir include")
        os.chdir("include")

        runCmd("wget https://github.com/vapoursynth/vapoursynth/archive/{0}.tar.gz".format(ver))
        runCmd("tar -xvf {0}.tar.gz vapoursynth-{0}/include".format(ver))

        runCmd("mv vapoursynth-{0}/include vapoursynth".format(ver))
        runCmd("rm -r vapoursynth-{0}".format(ver))
        runCmd("rm {0}.tar.gz".format(ver))
        os.chdir("..")

        runCmd("mkdir ../work2")

        runCmd("mv include ../work2")
        runCmd("mv lib ../work2")

        os.chdir("..")

        print("Installing to " + prefix)
        runCmd("rsync -aKv work2/ {0}".format(prefix))

        runCmd("rm -r work")
        runCmd("rm -r work2")

    elif sys.argv[1] == "uninstall":
        pass
    else:
        exitHelp()
