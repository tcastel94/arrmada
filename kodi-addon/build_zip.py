#!/usr/bin/env python3
"""Build script to create a zip file for the ArrMada Kodi add-on."""

import os
import shutil
import zipfile
from pathlib import Path


def package_addon():
    root_dir = Path(__file__).resolve().parent
    addon_dir = root_dir / "script.arrmada"
    output_zip_v131 = root_dir / "script.arrmada-1.3.1.zip"
    output_zip_v130 = root_dir / "script.arrmada-1.3.0.zip"
    output_zip_v124 = root_dir / "script.arrmada-1.2.4.zip"
    output_zip_v123 = root_dir / "script.arrmada-1.2.3.zip"
    output_zip_latest = root_dir / "script.arrmada.zip"
    output_zip_v122 = root_dir / "script.arrmada-1.2.2.zip"
    output_zip_v121 = root_dir / "script.arrmada-1.2.1.zip"
    output_zip_v120 = root_dir / "script.arrmada-1.2.0.zip"
    output_zip_v112 = root_dir / "script.arrmada-1.1.2.zip"
    output_zip_v111 = root_dir / "script.arrmada-1.1.1.zip"
    output_zip_v110 = root_dir / "script.arrmada-1.1.0.zip"
    output_zip_v109 = root_dir / "script.arrmada-1.0.9.zip"
    output_zip_v108 = root_dir / "script.arrmada-1.0.8.zip"
    output_zip_v107 = root_dir / "script.arrmada-1.0.7.zip"
    output_zip_v106 = root_dir / "script.arrmada-1.0.6.zip"
    output_zip_v105 = root_dir / "script.arrmada-1.0.5.zip"
    output_zip_v104 = root_dir / "script.arrmada-1.0.4.zip"
    output_zip_v103 = root_dir / "script.arrmada-1.0.3.zip"
    output_zip_v102 = root_dir / "script.arrmada-1.0.2.zip"
    output_zip_v101 = root_dir / "script.arrmada-1.0.1.zip"
    output_zip_v100 = root_dir / "script.arrmada-1.0.0.zip"

    if not addon_dir.exists():
        print(f"Error: {addon_dir} does not exist.")
        return

    print(f"Packaging {addon_dir} -> {output_zip_v131}...")

    with zipfile.ZipFile(output_zip_v131, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in sorted(addon_dir.rglob("*")):
            if file.is_file() and not file.name.startswith(".") and "__pycache__" not in str(file):
                arcname = file.relative_to(root_dir)
                zipf.write(file, arcname)
                print(f"  + {arcname}")

    shutil.copyfile(output_zip_v131, output_zip_latest)
    shutil.copyfile(output_zip_v131, output_zip_v130)
    shutil.copyfile(output_zip_v131, output_zip_v124)
    shutil.copyfile(output_zip_v123, output_zip_v121)
    shutil.copyfile(output_zip_v123, output_zip_v120)
    shutil.copyfile(output_zip_v123, output_zip_v112)
    shutil.copyfile(output_zip_v123, output_zip_v111)
    shutil.copyfile(output_zip_v123, output_zip_v110)
    shutil.copyfile(output_zip_v123, output_zip_v109)
    shutil.copyfile(output_zip_v123, output_zip_v108)
    shutil.copyfile(output_zip_v123, output_zip_v107)
    shutil.copyfile(output_zip_v123, output_zip_v106)
    shutil.copyfile(output_zip_v123, output_zip_v105)
    shutil.copyfile(output_zip_v123, output_zip_v104)
    shutil.copyfile(output_zip_v123, output_zip_v103)
    shutil.copyfile(output_zip_v123, output_zip_v102)
    shutil.copyfile(output_zip_v123, output_zip_v101)
    shutil.copyfile(output_zip_v123, output_zip_v100)
    print(f"Successfully generated:")
    print(f"  - {output_zip_v131}")
    print(f"  - {output_zip_latest}")















if __name__ == "__main__":
    package_addon()
