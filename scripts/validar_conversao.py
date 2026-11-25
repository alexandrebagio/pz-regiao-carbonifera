"""Verifica os TMX do WorldEd, os LOTs de teste e a instalação local do mod."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate_tmx(path: Path, expected: np.ndarray):
    doc = ET.parse(path).getroot()
    require(doc.get("width") == doc.get("height") == "256", f"TMX precisa ser 256x256: {path}")
    require(doc.get("orientation") == "levelisometric", f"Orientação TMX inválida: {path}")
    bitmap = doc.find("bmp-image[@index='0']")
    require(bitmap is not None, f"TMX sem bitmap de terreno: {path}")
    palette = np.array([[0, 0, 0]] + [list(map(int, c.get("rgb").split())) for c in bitmap.findall("color")], dtype=np.uint8)
    data = gzip.decompress(base64.b64decode(bitmap.findtext("pixels")))
    indices = np.frombuffer(data, dtype="<u4").reshape(256, 256)
    require(indices.max() < len(palette), f"Índice de paleta inválido: {path}")
    require(np.array_equal(palette[indices], expected), f"O bitmap TMX diverge do PNG original: {path}")
    for layer in doc.findall("layer"):
        require(layer.get("width") == layer.get("height") == "256", f"Camada com dimensões diferentes: {path}")
    return {"arquivo": str(path.relative_to(ROOT)), "camadas": len(doc.findall("layer")),
            "terreno_identico_ao_png": True}


def validate():
    setup = json.loads((ROOT / "mapping/teste_jogo.json").read_text(encoding="utf-8"))
    mod = Path(setup["mod_origem"])
    maps = mod / "common/media/maps" / setup["map_name"]
    terrain = np.array(Image.open(ROOT / "output/centro/terreno.png"))
    classes = np.load(ROOT / "output/centro/classes.npy", allow_pickle=False)
    require(np.all(terrain[classes == 2] == [100, 100, 100]), "Ruas precisam usar o RGB de asfalto escuro.")
    cfg = json.loads((ROOT / "config/centro.json").read_text(encoding="utf-8"))
    require(classes.shape == (cfg["tiles"], cfg["tiles"]), "Raster não corresponde à escala configurada.")
    roads = json.loads((ROOT / "output/centro/ruas.geojson").read_text(encoding="utf-8"))["features"]
    pedestrian = {"pedestrian", "footway", "path", "cycleway", "steps", "track"}
    road_widths = [f["properties"]["largura_gerada_tiles"] for f in roads
                   if f["properties"].get("highway") not in pedestrian]
    require(road_widths and min(road_widths) >= 8, "Via de veículos com menos de 8 tiles.")
    results = []
    for project_name in ("centro_criciuma.pzw", "teste_uma_celula.pzw"):
        project_path = ROOT / "mapping" / project_name
        project = ET.parse(project_path).getroot()
        require(project.get("cellFormat") == "native-256", "PZW fora da grade Native256.")
        cells = project.findall("cell")
        require(len(cells) == int(project.get("width"))*int(project.get("height")), "Faltam células associadas ao PZW.")
        for cell in cells:
            x, y = int(cell.get("x")), int(cell.get("y"))
            path = (project_path.parent / cell.get("map")).resolve()
            results.append(validate_tmx(path, terrain[y*256:(y+1)*256, x*256:(x+1)*256]))
    lot_results = []
    ox, oy = setup["origem_celulas"]
    for y in range(setup["dimensoes_celulas"][1]):
        for x in range(setup["dimensoes_celulas"][0]):
            gx, gy = ox+x, oy+y
            for name in (f"{gx}_{gy}.lotheader", f"world_{gx}_{gy}.lotpack", f"chunkdata_{gx}_{gy}.bin"):
                require((maps / name).is_file() and (maps / name).stat().st_size > 0, f"Binário ausente: {name}")
            source = (maps / f"world_{gx}_{gy}.lotpack.source").read_text(encoding="utf-8")
            chunks = re.findall(r"^chunk (\d+)\s*$", source, re.M)
            require(len(chunks) == len(set(chunks)) == 1024, f"Célula {gx},{gy} sem 1024 chunks únicos.")
            squares = re.findall(r"^\s+0,([0-7]),([0-7])\s*=\s*-?\d+\s*:\s*(\S[^\r\n]*)", source, re.M)
            require(len(squares) == 65536, f"Célula {gx},{gy} tem lacunas no piso: {len(squares)} quadrados.")
            header = (maps / f"{gx}_{gy}.lotheader.source").read_text(encoding="utf-8")
            for contents in (header, (maps / f"{gx}_{gy}.lotheader").read_bytes().decode("latin1")):
                streets = [int(i) for i in re.findall(r"blends_street_01_(\d+)\b", contents)]
                require(any(80 <= i <= 95 for i in streets), "Cabeçalho sem tiles de asfalto escuro.")
                require(not any(96 <= i <= 111 for i in streets), "A textura bege antiga ainda consta nos LOTs.")
            require("minLevel = 0" in header and "maxLevel = 0" in header, "Níveis inesperados no teste de terreno.")
            density = re.search(r"zombieDensity[^\{]*\{([^}]+)\}", header, re.S)
            require(density is not None and set(map(int, re.findall(r"\d+", density[1]))) == {0}, "Densidade de zumbis deveria ser zero.")
            biome = np.array(Image.open(maps / f"maps/biomemap_{gx}_{gy}.png").convert("RGB"))
            require(biome.shape == (256, 256, 3), "Biomemap com dimensões incorretas.")
            crop = classes[y*256:(y+1)*256, x*256:(x+1)*256]
            expected_green = np.full((256, 256), 115, dtype=np.uint8)
            expected_green[np.isin(crop, [2, 3])] = 64
            expected_green[crop == 4] = 0
            require(np.array_equal(biome[:, :, 1], expected_green) and not np.any(biome[:, :, [0, 2]]), "Canais de bioma/zona inválidos.")
            lot_results.append({"celula": [gx, gy], "chunks": len(chunks), "quadrados_piso": len(squares)})
    lx, ly = setup["spawn_local_tiles"]
    sx, sy, sz = setup["spawn_absoluto"]
    require((sx, sy, sz) == (ox*256+lx, oy*256+ly, 0), "Spawn global/local inconsistente.")
    require(np.all(classes[ly-1:ly+2, lx-1:lx+2] == 2), "Spawn sem área de asfalto suficiente.")
    spawn = (maps / "spawnpoints.lua").read_text(encoding="utf-8")
    require(f"posX = {sx}" in spawn and f"posY = {sy}" in spawn and "unemployed = pontos" in spawn,
            "Ponto de nascimento ausente no Lua.")
    require((mod / "42.0/mod.info").is_file() and (mod / "common/mod.info").is_file(), "Metadados B42 ausentes.")
    worldmap = ET.parse(maps / "worldmap.xml").getroot()
    require(worldmap.get("cellSize") == "256", "Worldmap fora da grade Native256.")
    cell_coords = {(int(c.get("x")), int(c.get("y"))) for c in worldmap.findall("cell")}
    nx, ny = setup["dimensoes_celulas"]
    require(cell_coords == {(ox+x, oy+y) for x in range(nx) for y in range(ny)}, "Worldmap desalinhado dos LOTs.")
    feature_count = len(worldmap.findall("cell/feature"))
    require(feature_count > 0, "Prévia vetorial vazia.")
    for cell in worldmap.findall("cell"):
        for feature in cell.findall("feature"):
            properties = {p.get("name"): p.get("value") for p in feature.findall("properties/property")}
            require(properties.get("highway") in {"secondary", "trail"} or properties.get("water") == "river",
                    "Propriedade worldmap sem estilo correspondente no jogo.")
            for ring in feature.findall("geometry/coordinates"):
                require(len(ring.findall("point")) >= 3, "Polígono worldmap incompleto.")
                require(all(0 <= float(p.get(a)) <= 256 for p in ring.findall("point") for a in ("x", "y")),
                        "Worldmap com vértice fora da célula.")
    require((maps / "worldmap.xml.bin").read_bytes().startswith(b"IGMB"), "Worldmap binário ausente ou inválido.")
    require((maps / "objects.lua").is_file(), "Arquivo de zonas do mapa ausente.")
    menu_script = mod / "common/media/lua/client/CRC_PreviewCriacao.lua"
    require(menu_script.is_file(), "Ajuste da prévia da criação ausente.")
    menu_source = menu_script.read_text(encoding="utf-8")
    require("__CRC_" not in menu_source and "localPreviewStyle" in menu_source,
            "Prévia da criação não foi parametrizada.")
    log = (ROOT / "mapping/validacao_lot_sources.log").read_text(encoding="utf-8")
    require(f"LOT source check completed: {nx*ny} cell(s)" in log, "Falta confirmação do validador LOT do WorldEd.")
    installed_count = 0
    if "mod_instalado" in setup:
        installed = Path(setup["mod_instalado"])
        registry = json.loads((installed / "instalacao_prototipo.json").read_text(encoding="utf-8"))
        for name, digest in registry["arquivos"].items():
            require(hashlib.sha256((installed / name).read_bytes()).hexdigest() == digest,
                    f"Instalação diverge do pacote: {name}")
            require(hashlib.sha256((mod / name).read_bytes()).hexdigest() == digest,
                    f"Pacote foi alterado após a instalação: {name}")
            installed_count += 1
    return {"status": "ok", "tmx": results, "lots": lot_results, "spawn": [sx, sy, sz],
            "asfalto": "RGB 100/100/100; familia blends_street_01_80..95 confirmada nos binarios",
            "worldmap": {"celulas": len(cell_coords), "feicoes": feature_count, "binario_IGMB": True},
            "vias_veiculos": {"segmentos": len(road_widths), "min_tiles": min(road_widths),
                              "max_tiles": max(road_widths), "tiles_mapa": cfg["tiles"]},
            "arquivos_instalados_verificados": installed_count,
            "limite": "v0.3: prévia da criação conferida em perfil isolado; cruzamento de dois carros pendente."}


if __name__ == "__main__":
    result = validate()
    (ROOT / "mapping/validacao_conversao.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
