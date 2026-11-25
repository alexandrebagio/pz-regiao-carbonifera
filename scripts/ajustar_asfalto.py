"""Migra os artefatos v0.1 para asfalto escuro e recompila LOTs com o WorldEd."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    settings = json.loads((ROOT / "config/ferramentas.json").read_text(encoding="utf-8"))
    tools = Path(settings["tools_dir"])
    exe = tools / "bin/PZWorldEd.exe"
    mod_dir = ROOT / "mod/RegiaoCarboniferaPrototipo/common/media/maps/CriciumaCentroTeste"
    backup = ROOT / "mapping/backups/antes_asfalto_v02"
    paths = list((ROOT / "mapping/tmx").rglob("*.tmx"))
    paths += [p for p in mod_dir.iterdir() if p.is_file() and
              (p.name.endswith((".lotheader", ".lotpack", ".bin", ".source")))]
    for path in paths:
        target = backup / path.relative_to(ROOT)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    changed_tmx = 0
    for path in (ROOT / "mapping/tmx").rglob("*.tmx"):
        doc = ET.parse(path)
        changed = False
        for color in doc.getroot().findall("bmp-image[@index='0']/color"):
            if color.get("rgb") == "120 120 120":
                color.set("rgb", "100 100 100")
                changed = True
        if changed:
            doc.write(path, encoding="utf-8", xml_declaration=True)
            changed_tmx += 1
    # Ambas as famílias possuem o mesmo arranjo de pisos/transições, em blocos de 16.
    # 96..111 = asfalto bege da primeira versão; 80..95 = asfalto escuro desta tilesheet.
    replaced = 0
    def substitute(match):
        nonlocal replaced
        tile = int(match[1])
        if 96 <= tile <= 111:
            replaced += 1
            return f"blends_street_01_{tile-16}"
        return match[0]
    for pattern in ("*.lotheader.source", "*.lotpack.source"):
        for path in mod_dir.glob(pattern):
            old = path.read_text(encoding="utf-8")
            new = re.sub(r"\bblends_street_01_(\d+)\b", substitute, old)
            if old != new:
                path.write_text(new, encoding="utf-8")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    for option, name, marker in (
        ("--check-lot-sources=", "validacao_lot_sources.log", "LOT source check completed: 4 cell(s)"),
        ("--import-lot-sources=", "recompilacao_asfalto.log", ""),
    ):
        log = ROOT / "mapping" / name
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([str(exe), option+str(mod_dir)], cwd=exe.parent,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=90,
                                    startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
        content = log.read_text(encoding="utf-8", errors="replace")
        if result.returncode != 0 or (marker and marker not in content):
            raise RuntimeError(f"Falha no WorldEd; veja {log}")
        print(content.splitlines()[-1])
    print(json.dumps({"tmx_atualizados": changed_tmx, "referencias_de_tiles_alteradas": replaced,
                      "backup": str(backup)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
