"""Configura os caminhos portáteis e prepara projetos Native256 sem sobrescrever PZW."""
from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def relative(path: Path, parent: Path) -> str:
    return Path(os.path.relpath(path, parent)).as_posix()


def prepare_project(path: Path, source: Path, cells: int, config: Path, export: Path):
    if path.exists():
        return "preservado (já existia)"
    export.mkdir(parents=True, exist_ok=True)
    world = ET.Element("world", version="1.0", width=str(cells), height=str(cells),
                       cellFormat="native-256")
    bmp = ET.SubElement(world, "BMPToTMX")
    for element, target in (("tmxexportdir", export), ("rulesfile", config / "Rules.txt"),
                            ("blendsfile", config / "Blends.txt"), ("mapbasefile", config / "MapBaseXML.txt")):
        ET.SubElement(bmp, element, path=relative(target, path.parent))
    for element, checked in (("assign-maps-to-world", True), ("warn-unknown-colors", True),
                             ("repair-unknown-colors", False), ("compress", True),
                             ("copy-pixels", True), ("update-existing", False), ("metadata-only", False)):
        ET.SubElement(bmp, element, checked=str(checked).lower())
    ET.SubElement(world, "bmp", path=relative(source, path.parent), x="0", y="0",
                  width=str(cells), height=str(cells))
    ET.indent(world, space=" ")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(world).write(path, encoding="utf-8", xml_declaration=True)
    return "criado"


def main():
    config = json.loads((ROOT / "config/ferramentas.json").read_text(encoding="utf-8"))
    tools, tiles, game = [Path(config[k]).resolve() for k in ("tools_dir", "tiles_dir", "game_dir")]
    for name in ("PZWorldEd.exe", "TileZed.exe", "BuildingEd.exe"):
        if not (tools / "bin" / name).is_file():
            raise FileNotFoundError(f"Editor ausente: {tools / 'bin' / name}")
    catalogs = tools / "config"
    for name in ("Rules.txt", "Blends.txt", "MapBaseXML.txt", "Tilesets.txt"):
        if not (catalogs / name).is_file():
            raise FileNotFoundError(f"Catálogo ausente: {catalogs / name}")
    if not (game / "media").is_dir():
        raise FileNotFoundError(f"Pasta do jogo ausente: {game}")
    pngs = list(tiles.rglob("*.png"))
    if not pngs:
        raise FileNotFoundError(f"Nenhuma tilesheet PNG em {tiles}")
    required = {"blends_natural_01", "blends_natural_02", "blends_street_01"}
    located = {p.stem: p for p in pngs if p.stem in required}
    if missing := required - located.keys():
        raise FileNotFoundError(f"Tilesheets básicas ausentes: {sorted(missing)}")
    for path in located.values():
        with Image.open(path) as image:
            image.verify()
    rules_text = (catalogs / "Rules.txt").read_text(encoding="utf-8-sig")
    ground_colors = set()
    for match in re.finditer(r"\brule\s*\{([^}]+)\}", rules_text):
        block = match[1]
        if not re.search(r"\bbitmap\s*=\s*0\b", block):
            continue
        color = re.search(r"\bcolor\s*=\s*(\d+)\s+(\d+)\s+(\d+)", block)
        if color:
            ground_colors.add(tuple(map(int, color.groups())))
    with Image.open(ROOT / "output/centro/terreno.png") as terrain:
        colors = set(map(tuple, np.unique(np.array(terrain).reshape(-1, 3), axis=0).tolist()))
    if unknown := colors - ground_colors:
        raise ValueError(f"Cores do terreno ausentes no Rules.txt instalado: {sorted(unknown)}")
    shared = tools / "settings/PZTools.ini"
    ini = configparser.ConfigParser(interpolation=None)
    ini.optionxform = str
    if shared.exists():
        ini.read(shared, encoding="utf-8-sig")
        backup = shared.with_suffix(".ini.antes-do-projeto")
        if not backup.exists():
            backup.write_bytes(shared.read_bytes())
    if not ini.has_section("Paths"):
        ini.add_section("Paths")
    for key, path in (("ConfigDirectory", catalogs), ("TilesDirectory", tiles),
                      ("ProjectZomboidDirectory", game)):
        ini.set("Paths", key, path.as_posix())
    shared.parent.mkdir(parents=True, exist_ok=True)
    with shared.open("w", encoding="utf-8", newline="\n") as stream:
        ini.write(stream, space_around_delimiters=False)
    mapping = ROOT / "mapping"
    statuses = {}
    geography = json.loads((ROOT / "config/centro.json").read_text(encoding="utf-8"))
    cells = geography["tiles"] // geography["tiles_por_celula"]
    for name, source, count, destination in (
        ("centro_criciuma.pzw", ROOT / "output/centro/terreno.png", cells, mapping / "tmx/centro"),
        ("teste_uma_celula.pzw", ROOT / "output/centro/celulas/centro_0_0.png", 1, mapping / "tmx/teste"),
    ):
        statuses[name] = prepare_project(mapping / name, source, count, catalogs, destination)
    report = {"tools_dir": str(tools), "tiles_dir": str(tiles), "game_dir": str(game),
              "tilesheets_png": len(pngs), "cores_terreno_aceitas": len(colors),
              "regras_instaladas": str(catalogs / "Rules.txt"), "projects": statuses,
              "nota": "Caminhos e cores verificados. TMX, LOT e teste no jogo ainda pendentes."}
    (mapping / "ambiente_worlded.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
