"""Cria células TMX por bitmap usando um template já convertido pelo WorldEd."""
from __future__ import annotations

import base64
import copy
import gzip
import json
from pathlib import Path
import shutil
import textwrap
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    cfg = json.loads((ROOT / "config/centro.json").read_text(encoding="utf-8"))
    count = cfg["tiles"] // cfg["tiles_por_celula"]
    texture = np.array(Image.open(ROOT / "output/centro/terreno.png").convert("RGB"))
    template = ET.parse(ROOT / "mapping/tmx/centro/terreno_0_0.tmx").getroot()
    backup = ROOT / "mapping/backups/antes_escala_v03"
    for path in list((ROOT / "mapping/tmx").rglob("*.tmx")):
        target = backup / path.relative_to(ROOT)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    for name, ncells, dest, prefix in (
        ("centro_criciuma.pzw", count, "centro", "terreno"),
        ("teste_uma_celula.pzw", 1, "teste", "centro_0_0"),
    ):
        pzw_path = ROOT / "mapping" / name
        project = ET.parse(pzw_path)
        world = project.getroot()
        world.set("width", str(ncells)); world.set("height", str(ncells))
        for cell in world.findall("cell"):
            world.remove(cell)
        for bmp in world.findall("bmp"):
            bmp.set("width", str(ncells)); bmp.set("height", str(ncells))
        for y in range(ncells):
            for x in range(ncells):
                raster = texture[y*256:(y+1)*256, x*256:(x+1)*256]
                colors, inverse = np.unique(raster.reshape(-1, 3), axis=0, return_inverse=True)
                cell_map = copy.deepcopy(template)
                for node in cell_map.findall("bmp-image"):
                    cell_map.remove(node)
                bmp_image = ET.SubElement(cell_map, "bmp-image", index="0", seed="1")
                for color in colors:
                    ET.SubElement(bmp_image, "color", rgb=" ".join(map(str, color.tolist())))
                indices = (inverse.astype("<u4")+1).tobytes()
                pixels = ET.SubElement(bmp_image, "pixels")
                pixels.text = "\n"+"\n".join(textwrap.wrap(base64.b64encode(gzip.compress(indices, mtime=0)).decode(), 76))+"\n"
                filename = f"{prefix}_{x}_{y}.tmx"
                path = ROOT / "mapping/tmx" / dest / filename
                ET.ElementTree(cell_map).write(path, encoding="utf-8", xml_declaration=True)
                ET.SubElement(world, "cell", x=str(x), y=str(y), map=f"tmx/{dest}/{filename}")
        ET.indent(project, space=" ")
        project.write(pzw_path, encoding="utf-8", xml_declaration=True)
    # Native256 usa 32 amostras de densidade por célula.
    Image.new("RGB", (count*32, count*32), (0, 0, 0)).save(ROOT / "output/centro/zombiespawn.png")
    print(f"Projeto expandido: {count}x{count} células; {count*count+1} TMX preparados.")


if __name__ == "__main__":
    main()
