"""Gera o mapa vetorial usado na seleção de local e no mapa do jogo B42."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
from rasterio.features import shapes
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]


def generate(map_dir: Path, origin: tuple[int, int], classes: np.ndarray) -> dict:
    world = ET.Element("world", version="1.0", cellSize="256")
    count = 0
    # Não desenhar contornos de edifícios que ainda não existem no mapa jogável.
    filters = {2: ("highway", "secondary"), 3: ("highway", "trail"), 4: ("water", "river")}
    for cy in range(classes.shape[0] // 256):
        for cx in range(classes.shape[1] // 256):
            cell = ET.SubElement(world, "cell", x=str(origin[0]+cx), y=str(origin[1]+cy))
            crop = classes[cy*256:(cy+1)*256, cx*256:(cx+1)*256]
            mask = np.isin(crop, list(filters))
            for geometry, value in shapes(crop, mask=mask, connectivity=4):
                polygon = shape(geometry)
                if polygon.is_empty or polygon.area < 1:
                    continue
                feature = ET.SubElement(cell, "feature")
                geom = ET.SubElement(feature, "geometry", type="Polygon")
                for ring in [polygon.exterior, *polygon.interiors]:
                    coordinates = ET.SubElement(geom, "coordinates")
                    # Fechamento implícito, como nos arquivos escritos pelo WorldEd.
                    for x, y in list(ring.coords)[:-1]:
                        ET.SubElement(coordinates, "point", x=str(round(x)), y=str(round(y)))
                properties = ET.SubElement(feature, "properties")
                key, val = filters[int(value)]
                ET.SubElement(properties, "property", name=key, value=val)
                count += 1
    ET.indent(world, space=" ")
    source = ROOT / "mapping/worldmap_fonte.xml"
    ET.ElementTree(world).write(source, encoding="utf-8", xml_declaration=True)
    tools = json.loads((ROOT / "config/ferramentas.json").read_text(encoding="utf-8"))
    exe = Path(tools["tools_dir"]) / "bin/PZWorldEd.exe"
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    log = ROOT / "mapping/validacao_worldmap.log"
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run([str(exe), f"--validate-ingamemap={source}"],
                                cwd=exe.parent, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=90, startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
    output = log.read_text(encoding="utf-8", errors="replace")
    if result.returncode != 0 or "InGameMap validation passed:" not in output:
        raise RuntimeError(f"WorldEd não aprovou o worldmap. Veja {log}")
    # Publicar somente a saída normalizada pelo escritor do próprio editor.
    shutil.copy2(Path(str(source)+".validated.xml"), map_dir / "worldmap.xml")
    shutil.copy2(Path(str(source)+".validated.bin"), map_dir / "worldmap.xml.bin")
    return {"features_fonte": count, "cell_size": 256, "validado_worlded": True,
            "arquivos": ["worldmap.xml", "worldmap.xml.bin"]}


if __name__ == "__main__":
    report = json.loads((ROOT / "mapping/teste_jogo.json").read_text(encoding="utf-8"))
    target = Path(report["mod_origem"]) / "common/media/maps" / report["map_name"]
    print(json.dumps(generate(target, tuple(report["origem_celulas"]),
                              np.load(ROOT / "output/centro/classes.npy", allow_pickle=False)), indent=2))
