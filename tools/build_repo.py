#!/usr/bin/env python3
"""Pack addon zips and write Kodi repository index files under repo/."""
import hashlib
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "repo"
ADDONS = [
    "repository.ambientwled",
    "script.module.ambientwled",
    "script.service.ambientwled",
    "plugin.program.ambientwled",
]
SKIP = {".git", "__pycache__", ".DS_Store"}


def version_of(addon_dir: Path) -> str:
    tree = ET.parse(addon_dir / "addon.xml")
    return tree.getroot().attrib["version"]


def zip_addon(addon_id: str) -> Path:
    src = ROOT / addon_id
    ver = version_of(src)
    out_dir = REPO / "zips" / addon_id
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{addon_id}-{ver}.zip"
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in src.rglob("*"):
            if any(part in SKIP for part in path.parts):
                continue
            if path.is_file():
                zf.write(path, path.relative_to(ROOT).as_posix())
    return dest


def addons_xml() -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<addons>"]
    for addon_id in ADDONS:
        xml = (ROOT / addon_id / "addon.xml").read_text(encoding="utf-8")
        xml = xml.replace('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "").strip()
        parts.append(xml)
    parts.append("</addons>\n")
    return "\n".join(parts)


def main():
    REPO.mkdir(exist_ok=True)
    for addon_id in ADDONS:
        dest = zip_addon(addon_id)
        print("wrote", dest.relative_to(ROOT))
    xml = addons_xml()
    xml_path = REPO / "addons.xml"
    xml_path.write_text(xml, encoding="utf-8")
    digest = hashlib.md5(xml.encode("utf-8")).hexdigest()
    (REPO / "addons.xml.md5").write_text(digest + "\n", encoding="utf-8")
    print("wrote repo/addons.xml")
    print("md5", digest)


if __name__ == "__main__":
    main()
