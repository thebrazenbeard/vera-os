#!/usr/bin/env python3
"""Source-only compatibility probe for a pinned VeraOS resident Buildroot candidate."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
def probe(source: Path, repo: Path = ROOT):
    contract=json.loads((repo/"architecture/os/VERA_OS_RESIDENT_BUILDROOT_CANDIDATE_V1.json").read_text())
    source=source.resolve(strict=True)
    commit=subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()
    if commit!=contract["candidate"]["peeled_git_commit"]:
        raise ValueError("Buildroot source commit is not the pinned peeled tag commit")
    status=subprocess.check_output(["git","-C",str(source),"status","--porcelain=v1"],text=True).strip()
    if status: raise ValueError("Buildroot checkout is modified")
    python=(source/"package/python3/python3.mk").read_text()
    major=re.search(r"^PYTHON3_VERSION_MAJOR\s*=\s*([0-9]+\.[0-9]+)\s*$",python,re.M)
    suffix=re.search(r"^PYTHON3_VERSION\s*=\s*\$\(PYTHON3_VERSION_MAJOR\)\.([0-9]+)\s*$",python,re.M)
    if not major or not suffix: raise ValueError("Unsupported upstream Python version binding")
    version=f"{major.group(1)}.{suffix.group(1)}"
    if version!=contract["candidate"]["target_python_expected"]:
        raise ValueError("Actual pinned Python version differs from candidate")
    defconfig=(repo/contract["candidate"]["source_defconfig"]).read_text()
    package_sources={}
    missing=[]
    for pkg in contract["requires"]["python_packages"]:
        stem=pkg["package"]
        mk=source/f"package/{stem}/{stem}.mk"
        config=source/f"package/{stem}/Config.in"
        if not mk.is_file() or not config.is_file():
            raise ValueError("Buildroot dependency package missing: "+stem)
        target=re.search(r"^"+re.escape(stem.upper().replace("-","_"))+r"_VERSION\s*=\s*([^\s]+)",mk.read_text(),re.M)
        if not target or target.group(1)!=pkg["version"]:
            raise ValueError("Unexpected upstream dependency version: "+stem)
        symbol=pkg["symbol"]
        if not re.search(r"^config\s+"+re.escape(symbol)+r"\s*$",config.read_text(),re.M):
            raise ValueError("Upstream dependency Kconfig missing: "+symbol)
        if f"{symbol}=y" not in defconfig.splitlines(): missing.append(symbol)
        package_sources[stem]=target.group(1)
    for flag in contract["requires"]["browser_flags"]:
        if f"{flag}=y" not in defconfig.splitlines(): missing.append(flag)
    if missing: raise ValueError("Resident defconfig missing required flags: "+",".join(missing))
    return {
      "schema":"VERA_OS_RESIDENT_UPSTREAM_SOURCE_PROBE_V1",
      "status":"PINNED_SOURCE_SYMBOLS_VERIFIED_KCONFIG_NOT_RUN",
      "pinned_commit":commit,
      "expected_python":version,
      "python_dependency_versions":package_sources,
      "profile":contract["candidate"]["source_defconfig"],
      "browser_kconfig_resolved":False,
      "cross_compilation_qualified":False,
      "image_built":False,
      "resident_runtime_qualified":False,
      "protected_effect_authority":False
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--buildroot",type=Path,required=True)
    p.add_argument("--repo-root",type=Path,default=ROOT)
    args=p.parse_args()
    print(json.dumps(probe(args.buildroot,args.repo_root),indent=2))
if __name__=="__main__":
    main()
