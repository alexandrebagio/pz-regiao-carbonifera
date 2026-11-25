"""Confere dimensões, paleta, georreferência, vetores e reconstrução das células."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(out: Path) -> dict:
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    cfg = manifest["config"]
    n, cell = cfg["tiles"], cfg["tiles_por_celula"]
    terrain_image = Image.open(out / "terreno.png")
    require(terrain_image.mode == "RGB", "Terreno precisa ser RGB, sem transparência.")
    require(terrain_image.size == (n, n), "Dimensões incorretas do terreno.")
    terrain = np.array(terrain_image)
    allowed = {tuple(c["rgb"]) for c in manifest["classes"]}
    colors = set(map(tuple, np.unique(terrain.reshape(-1, 3), axis=0).tolist()))
    require(colors <= allowed, f"Cores desconhecidas: {colors - allowed}")
    classes = np.load(out / "classes.npy", allow_pickle=False)
    require(classes.shape == (n, n), "Dimensões incorretas das classes.")
    for item in manifest["classes"]:
        mask = classes == item["id"]
        require(int(mask.sum()) == item["pixels"], "Contagem de classe incorreta.")
        require(np.all(terrain[mask] == item["rgb"]), "Paleta diverge da classificação.")
    require(sum(c["pixels"] for c in manifest["classes"]) == n*n, "Classe desconhecida no raster.")
    for name in ("terreno_veg.png", "vegetacao.png"):
        image = Image.open(out / name)
        require(image.mode == "RGB" and image.size == (n, n), f"Vegetação inválida: {name}")
        require(not np.any(np.array(image)), "Este protótipo deve ter vegetação vazia.")
    reconstructed = np.zeros_like(terrain)
    seen = set()
    for item in manifest["celulas"]:
        x, y = item["x_local"], item["y_local"]
        require(0 <= x < n//cell and 0 <= y < n//cell and (x, y) not in seen, "Célula duplicada/fora do mapa.")
        seen.add((x, y))
        piece = Image.open(out / item["terreno"])
        require(piece.mode == "RGB" and piece.size == (cell, cell), "Célula inválida.")
        reconstructed[y*cell:(y+1)*cell, x*cell:(x+1)*cell] = np.array(piece)
        veg = Image.open(out / item["vegetacao"])
        require(veg.size == piece.size and veg.mode == "RGB" and not np.any(np.array(veg)), "Vegetação da célula inválida.")
    require(len(seen) == (n//cell)**2, "Faltam células.")
    require(np.array_equal(terrain, reconstructed), "Emendas das células divergem do terreno.")
    xmin, ymin, xmax, ymax = manifest["geografia"]["bounds_utm"]
    a, b, c, d, e, f = manifest["geografia"]["affine_pixel_to_utm"]
    require(abs(a-cfg["metros_por_tile"]) < 1e-7 and abs(e+a) < 1e-7 and b == d == 0,
            "Escala ou orientação incorreta.")
    require(abs(c-xmin) < 1e-7 and abs(f-ymax) < 1e-7, "Origem raster incorreta.")
    center = cfg["centro"]
    x, y = Transformer.from_crs(4326, cfg["crs_metrico"], always_xy=True).transform(
        center["longitude"], center["latitude"])
    require(abs((x-c)/a-n/2) < 1e-6 and abs((y-f)/e-n/2) < 1e-6, "Praça fora do centro.")
    tiles = json.loads((out / "edificios_tiles.json").read_text(encoding="utf-8"))
    geographic = json.loads((out / "edificios.geojson").read_text(encoding="utf-8"))
    require(len(tiles["features"]) == len(geographic["features"]), "Contagens de edifícios divergentes.")
    for feature in tiles["features"]:
        geom = shape(feature["geometry"])
        bounds = geom.bounds
        require(geom.is_valid and not geom.is_empty and min(bounds) >= -1e-6 and max(bounds) <= n+1e-6,
                "Contorno de edifício inválido ou fora do recorte.")
    for name in ("edificios.geojson", "ruas.geojson"):
        doc = json.loads((out / name).read_text(encoding="utf-8"))
        for feature in doc["features"]:
            geom = shape(feature["geometry"])
            west, south, east, north = geom.bounds
            require(geom.is_valid and -180 <= west <= east <= 180 and -90 <= south <= north <= 90,
                    "GeoJSON precisa conter coordenadas geográficas válidas.")
    snapshot = ROOT / manifest["osm"]["snapshot"]
    require(hashlib.sha256(snapshot.read_bytes()).hexdigest() == manifest["osm"]["sha256"], "Snapshot alterado.")
    return {"status": "ok", "dimensoes": [n, n], "celulas": len(seen),
            "cores_terreno": len(colors), **manifest["contagens"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/centro")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.output), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"ERRO: {exc}\n")
