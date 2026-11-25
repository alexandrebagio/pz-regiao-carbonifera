"""Completa o mod exportado pelo WorldEd e instala uma cópia local de teste."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

if __package__:
    from .gerar_worldmap import generate as generate_worldmap
else:
    from gerar_worldmap import generate as generate_worldmap

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MOD_ID = "RegiaoCarboniferaPrototipo"
MAP_NAME = "CriciumaCentroTeste"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_mod(source: Path, destination: Path):
    """Só substitui arquivos ainda idênticos aos instalados por este script."""
    marker = destination / "instalacao_prototipo.json"
    previous = {}
    if destination.exists():
        if not marker.is_file():
            raise FileExistsError(f"Pasta já existente sem registro deste instalador: {destination}")
        previous = json.loads(marker.read_text(encoding="utf-8"))["arquivos"]
    selected = [p for p in source.rglob("*") if p.is_file() and ".source" not in p.name]
    copied = {}
    # Verificar todos os conflitos antes de copiar qualquer arquivo.
    for path in selected:
        name = path.relative_to(source).as_posix()
        target = destination / name
        if target.exists() and digest(target) not in {digest(path), previous.get(name)}:
            raise FileExistsError(f"Arquivo local alterado; preservado: {target}")
        copied[name] = digest(path)
    for path in selected:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    marker.write_text(json.dumps({"mod_id": MOD_ID, "origem": str(source), "arquivos": copied},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    return len(copied)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instalar", action="store_true", help="Copia o mod para Zomboid/mods; não o habilita.")
    args = parser.parse_args()
    project = ET.parse(ROOT / "mapping/centro_criciuma.pzw").getroot()
    origin = tuple(map(int, project.find("GenerateLots/worldOrigin").get("origin").split(",")))
    if project.get("cellFormat") != "native-256":
        raise ValueError("O mod de teste exige Native256.")
    cells_x, cells_y = int(project.get("width")), int(project.get("height"))
    classes = np.load(ROOT / "output/centro/classes.npy", allow_pickle=False)
    if classes.shape != (cells_y*256, cells_x*256):
        raise ValueError("Dimensões do raster e do PZW não coincidem.")
    mod = ROOT / "mod" / MOD_ID
    map_dir = mod / "common/media/maps" / MAP_NAME
    for y in range(cells_y):
        for x in range(cells_x):
            gx, gy = origin[0]+x, origin[1]+y
            for name in (f"{gx}_{gy}.lotheader", f"world_{gx}_{gy}.lotpack", f"chunkdata_{gx}_{gy}.bin"):
                if not (map_dir / name).is_file():
                    raise FileNotFoundError(f"Exporte os LOTs no WorldEd antes: {map_dir / name}")
    # Ponto de nascimento perto da praça, com 3x3 pixels de asfalto ao redor.
    road = classes == 2
    h, w = road.shape
    padded = np.pad(road, 1, constant_values=False)
    safe = np.logical_and.reduce([padded[dy:dy+h, dx:dx+w] for dy in range(3) for dx in range(3)])
    candidates = np.argwhere(safe)
    if not len(candidates):
        raise ValueError("Nenhum ponto de asfalto com espaço suficiente para nascer.")
    y, x = map(int, candidates[np.argmin(np.sum((candidates - np.array([h/2, w/2]))**2, axis=1))])
    spawn_x, spawn_y = origin[0]*256+x, origin[1]*256+y
    professions = project.find("propertyenum[@name='Professions']")
    names = professions.get("choices").split(",") if professions is not None else ["unemployed"]
    names = sorted(set(names) | {"unemployed"})
    lua = ("-- Build 42: coordenadas absolutas; um ponto comum para todas as profissoes.\n"
           "function SpawnPoints()\n"
           f"    local pontos = {{ {{ posX = {spawn_x}, posY = {spawn_y}, posZ = 0 }} }}\n"
           "    return {\n" + "".join(f"        {name} = pontos,\n" for name in names) + "    }\nend\n")
    (map_dir / "spawnpoints.lua").write_text(lua, encoding="utf-8")
    (map_dir / "map.info").write_text(
        "title=Criciuma - Centro (Prototipo)\n"
        "lots=Muldraugh, KY\nfixed2x=true\n"
        "description=Prototipo 0.3: mapa ampliado, ruas de duas faixas e avenidas largas. Sem edificios jogaveis.\n"
        f"zoomX={spawn_x}\nzoomY={spawn_y}\nzoomS=13.5\n", encoding="utf-8")
    (map_dir / "objects.lua").write_text("-- Sem zonas manuais nesta etapa.\nobjects = {}\n", encoding="utf-8")
    for folder in ("common", "42.0"):
        (mod / folder).mkdir(parents=True, exist_ok=True)
        (mod / folder / "mod.info").write_text(
            f"name=Criciuma - Prototipo Centro\nid={MOD_ID}\n"
            "description=Prototipo 0.3: mapa 1024x1024, ruas de 8 a 14 tiles e previa da criacao. Crie um mundo novo. Dados: OpenStreetMap contributors (ODbL).\n"
            "poster=poster.png\n", encoding="utf-8")
    # B42: IDs numéricos por tile, não a paleta de terreno do WorldEd.
    # Red 0 = sem bioma procedural; Green 115 = TownZone; 64 = ForagingNav; 0 = Water.
    biomes = np.zeros((*classes.shape, 3), dtype=np.uint8)
    biomes[:, :, 1] = 115
    biomes[np.isin(classes, [2, 3]), 1] = 64
    biomes[classes == 4, 1] = 0
    maps_dir = map_dir / "maps"
    maps_dir.mkdir(exist_ok=True)
    for cy in range(cells_y):
        for cx in range(cells_x):
            Image.fromarray(biomes[cy*256:(cy+1)*256, cx*256:(cx+1)*256]).save(
                maps_dir / f"biomemap_{origin[0]+cx}_{origin[1]+cy}.png")
    # Miniatura geográfica, sem copiar tilesheets do jogo para o mod.
    thumb = Image.open(ROOT / "output/centro/terreno.png").convert("RGB").resize((256, 256), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(thumb)
    draw.rectangle((0, 0, 256, 42), fill=(30, 45, 40))
    font_path = Path("C:/Windows/Fonts/segoeuib.ttf")
    font = ImageFont.truetype(str(font_path), 23) if font_path.exists() else ImageFont.load_default(size=23)
    draw.text((12, 6), "CRICIUMA / PZ", fill="white", font=font)
    thumb.save(map_dir / "thumb.png")
    thumb.save(mod / "common/poster.png")
    thumb.save(mod / "42.0/poster.png")
    shutil.copy2(ROOT / "output/centro/ATRIBUICAO.txt", mod / "ATRIBUICAO.txt")
    worldmap = generate_worldmap(map_dir, origin, classes)
    menu_source = (ROOT / "config/CRC_PreviewCriacao.lua").read_text(encoding="utf-8")
    for token, value in {"__CRC_MIN_X__": origin[0]*256, "__CRC_MIN_Y__": origin[1]*256,
                         "__CRC_MAX_X__": (origin[0]+cells_x)*256-1,
                         "__CRC_MAX_Y__": (origin[1]+cells_y)*256-1}.items():
        menu_source = menu_source.replace(token, str(value))
    menu_target = mod / "common/media/lua/client/CRC_PreviewCriacao.lua"
    menu_target.parent.mkdir(parents=True, exist_ok=True)
    menu_target.write_text(menu_source, encoding="utf-8")
    report = {"mod_id": MOD_ID, "map_name": MAP_NAME, "origem_celulas": list(origin),
              "dimensoes_celulas": [cells_x, cells_y], "spawn_absoluto": [spawn_x, spawn_y, 0],
              "spawn_local_tiles": [x, y], "zombiespawn": f"{cells_x*32}x{cells_y*32} RGB preto; densidade exportada zero",
              "biomemap": "red=0; green=115 terreno, 64 vias, 0 agua; blue=0",
              "mod_origem": str(mod), "worldmap": worldmap,
              "validacao_no_jogo": "v0.3: ruas ampliadas e prévia da criação precisam de novo teste visual."}
    if args.instalar:
        target = Path(os.environ["USERPROFILE"]) / "Zomboid/mods" / MOD_ID
        report["arquivos_instalados"] = install_mod(mod, target)
        report["mod_instalado"] = str(target)
    (ROOT / "mapping/teste_jogo.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
