"""OSM -> terreno RGB, células Native256 e vetores para o protótipo de Criciúma."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import sys

import geopandas as gpd
import numpy as np
import osmnx as ox
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely import affinity, make_valid
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
TAGS = {
    "highway": True,
    "building": True,
    "leisure": ["park", "garden"],
    "landuse": ["grass", "forest", "meadow", "recreation_ground", "village_green"],
    "natural": ["water", "wood", "grassland", "scrub", "wetland"],
    "waterway": ["river", "stream", "canal", "drain"],
    "amenity": ["parking"],
}
# Cores de bitmap=0 consultadas em Rules.txt; não aplicar suavização aos PNGs.
PALETTE = np.array([
    (117, 117, 47),  # Medium Grass: fundo provisório, sem classificação completa
    (90, 100, 35),   # Dark Grass: parques/áreas verdes
    (100, 100, 100), # Dark Asphalt: vias/estacionamentos (família blends_street_01_80)
    (80, 80, 80),    # Gravel Asphalt: caminhos provisórios
    (0, 138, 255),   # Water
], dtype=np.uint8)
PREVIEW_PALETTE = np.array([
    (216, 220, 201), (132, 173, 122), (77, 90, 101),
    (168, 163, 143), (94, 165, 198),
], dtype=np.uint8)
RULES_SOURCE = (
    "https://github.com/Unjammer/PZ_Mapping_Tools/blob/"
    "7ebfa7a6644f8652a81de35bf86d2fa4153bedb1/WorldEd/Rules.txt"
)
ROAD_TILES = {
    "motorway": 16, "motorway_link": 10, "trunk": 14, "trunk_link": 10,
    "primary": 14, "primary_link": 10, "secondary": 12, "secondary_link": 10,
    "tertiary": 10, "tertiary_link": 8, "residential": 8,
    "unclassified": 8, "living_street": 8, "service": 8, "road": 8,
}
PATHS = {"pedestrian", "footway", "path", "cycleway", "steps", "track"}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
                         encoding="utf-8")
    temporary.replace(path)


def read_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    for key in ("tiles", "tiles_por_celula"):
        if type(cfg[key]) is not int or cfg[key] <= 0:
            raise ValueError(f"{key} deve ser inteiro positivo.")
    if cfg["tiles"] > 8192 or cfg["tiles"] % cfg["tiles_por_celula"]:
        raise ValueError("tiles deve ser múltiplo de tiles_por_celula e <= 8192.")
    for key in ("metros_por_tile", "largura_minima_rua_tiles", "largura_minima_caminho_tiles"):
        if not math.isfinite(cfg[key]) or cfg[key] <= 0:
            raise ValueError(f"{key} deve ser positivo e finito.")
    if not math.isfinite(cfg["margem_consulta_m"]) or cfg["margem_consulta_m"] < 0:
        raise ValueError("margem_consulta_m deve ser não negativa e finita.")
    c = cfg["centro"]
    if not (-90 < c["latitude"] < 90 and -180 <= c["longitude"] <= 180):
        raise ValueError("Coordenadas do centro inválidas.")
    if not cfg["crs_metrico"].upper().startswith("EPSG:327"):
        raise ValueError("Este protótipo espera WGS84 / UTM sul, em metros (EPSG:327xx).")
    return cfg


def area_for(cfg: dict):
    c = cfg["centro"]
    project = Transformer.from_crs("EPSG:4326", cfg["crs_metrico"], always_xy=True)
    x, y = project.transform(c["longitude"], c["latitude"])
    half = cfg["tiles"] * cfg["metros_por_tile"] / 2
    return box(x-half, y-half, x+half, y+half)


def query_spec(cfg: dict, area) -> dict:
    return {"bounds_utm": list(area.bounds), "crs": cfg["crs_metrico"],
            "margin_m": cfg["margem_consulta_m"], "tags": TAGS}


def fetch_features(cfg: dict, area, *, offline: bool, refresh: bool):
    spec = query_spec(cfg, area)
    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]
    snapshot = ROOT / "data/raw" / f"osm_{key}.geojson"
    if snapshot.exists() and not refresh:
        print(f"Usando snapshot local: {snapshot.relative_to(ROOT)}", flush=True)
        doc = json.loads(snapshot.read_text(encoding="utf-8"))
        return gpd.GeoDataFrame.from_features(doc["features"], crs="EPSG:4326"), doc["provenance"], snapshot
    if offline:
        raise FileNotFoundError(f"Snapshot ausente para esta área: {snapshot}. Execute sem --offline primeiro.")
    ox.settings.use_cache = not refresh
    ox.settings.cache_folder = str(ROOT / "data/raw/osmnx_cache")
    ox.settings.requests_timeout = 90
    ox.settings.overpass_url = cfg["overpass_url"]
    ox.settings.http_user_agent = "PZ-Regiao-Carbonifera/0.1 (local OSM mapping prototype)"
    ox.settings.log_console = False
    ox.settings.log_file = True
    ox.settings.logs_folder = str(ROOT / "data/raw/logs")
    # Consulta com margem ANTES do recorte: preserva ruas junto à borda.
    query_area = gpd.GeoSeries([area.buffer(cfg["margem_consulta_m"])],
                              crs=cfg["crs_metrico"]).to_crs(4326).iloc[0]
    print("Consultando OpenStreetMap via Overpass...", flush=True)
    frame = ox.features_from_polygon(query_area, TAGS).reset_index()
    frame = frame.rename(columns={"element": "osm_type", "id": "osm_id"})
    if frame.empty:
        raise ValueError("O OpenStreetMap não retornou feições para a área.")
    # GeoJSON mantém os atributos OSM e as geometrias antes do recorte final.
    doc = json.loads(frame.to_json(drop_id=True, to_wgs84=True))
    provenance = {
        "snapshot_utc": datetime.now(timezone.utc).isoformat(),
        "query": spec, "overpass_url": cfg["overpass_url"],
        "attribution": "© OpenStreetMap contributors",
        "license": "https://www.openstreetmap.org/copyright",
        "note": "Horário da consulta; o instante de atualização da base OSM pode ser anterior.",
    }
    doc["provenance"] = provenance
    write_json(snapshot, doc)
    # Reabrir uniformiza tipos com a execução offline.
    return gpd.GeoDataFrame.from_features(doc["features"], crs="EPSG:4326"), provenance, snapshot


def tag(row, key: str) -> str:
    value = row.get(key)
    return value if isinstance(value, str) else ""


def polygon_parts(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if hasattr(geom, "geoms"):
        return [p for child in geom.geoms for p in polygon_parts(child)]
    return []


def road_width(row, cfg: dict) -> float:
    kind = tag(row, "highway")
    minimum = cfg["largura_minima_caminho_tiles"] if kind in PATHS else cfg["largura_minima_rua_tiles"]
    tiles = max(minimum, ROAD_TILES.get(kind, minimum))
    # width do OSM em metros; valores não métricos/ambíguos usam a largura padrão.
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:m)?\s*", tag(row, "width"))
    if match:
        tiles = max(tiles, min(float(match[1].replace(",", ".")) / cfg["metros_por_tile"], 32))
    return tiles * cfg["metros_por_tile"]


def build_layers(frame: gpd.GeoDataFrame, cfg: dict, area):
    projected = frame.to_crs(cfg["crs_metrico"]).copy()
    projected.geometry = projected.geometry.map(make_valid)
    n = cfg["tiles"]
    transform = from_bounds(*area.bounds, n, n)
    greens, waters, paths, roads, buildings, streets = [], [], [], [], [], []
    for _, row in projected.iterrows():
        geom = row.geometry
        clipped = geom.intersection(area)
        properties = {k: row[k] for k in ("osm_type", "osm_id", "name", "building", "highway", "amenity")
                      if k in row and (isinstance(row[k], (str, int)) or isinstance(row[k], np.integer))}
        if tag(row, "building") and tag(row, "building") != "no":
            for part in polygon_parts(clipped):
                buildings.append({**properties, "geometry": part,
                                  "area_real_m2": part.area,
                                  "area_reduzida_tiles2": part.area / cfg["metros_por_tile"]**2})
        polygons = polygon_parts(clipped)
        green = (tag(row, "leisure") in {"park", "garden"}
                 or tag(row, "landuse") in TAGS["landuse"]
                 or tag(row, "natural") in {"wood", "grassland", "scrub", "wetland"})
        if green:
            greens.extend((part, 1) for part in polygons)
        if tag(row, "natural") == "water" or tag(row, "waterway") in TAGS["waterway"]:
            if polygons:
                waters.extend((part, 4) for part in polygons)
            elif geom.geom_type in {"LineString", "MultiLineString"}:
                # Largura provisória: não representa medição hidrológica.
                waters.append((geom.buffer(cfg["metros_por_tile"]).intersection(area), 4))
        if tag(row, "amenity") == "parking":
            roads.extend((part, 2) for part in polygons)
        highway = tag(row, "highway")
        if highway in ROAD_TILES or highway in PATHS:
            destination, value = (paths, 3) if highway in PATHS else (roads, 2)
            if geom.geom_type in {"LineString", "MultiLineString"}:
                # Evitar colapsar passagens elevadas/subterrâneas no plano do solo.
                if tag(row, "tunnel") not in {"", "no"} or tag(row, "bridge") not in {"", "no"}:
                    continue
                surface = geom.buffer(road_width(row, cfg)/2, cap_style="square").intersection(area)
                if not surface.is_empty:
                    destination.append((surface, value))
                    if not clipped.is_empty:
                        streets.append({**properties, "geometry": clipped,
                                        "largura_gerada_tiles": road_width(row, cfg)/cfg["metros_por_tile"]})
            elif tag(row, "area") == "yes":
                destination.extend((part, value) for part in polygons)
    shapes = [(g, v) for g, v in greens + waters + paths + roads if not g.is_empty]
    # Ruas por último: permitem travessias; cruzamentos/níveis exigem revisão manual.
    classes = (rasterize(shapes, out_shape=(n, n), transform=transform,
                         fill=0, dtype="uint8", all_touched=False)
               if shapes else np.zeros((n, n), dtype=np.uint8))
    projected.geometry = projected.geometry.intersection(area)
    projected = projected[~projected.geometry.is_empty].copy()
    return classes, buildings, streets, projected, transform


def vector_frame(records: list[dict], crs: str) -> gpd.GeoDataFrame:
    if not records:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=crs)
    return gpd.GeoDataFrame(records, geometry="geometry", crs=crs)


def save_vectors(out: Path, buildings: list[dict], streets: list[dict], cfg: dict, area):
    bdf = vector_frame(buildings, cfg["crs_metrico"])
    rdf = vector_frame(streets, cfg["crs_metrico"])
    for name, frame in (("edificios", bdf), ("ruas", rdf)):
        write_json(out / f"{name}.geojson", json.loads(frame.to_json(drop_id=True, to_wgs84=True)))
    # Coordenadas contínuas locais, origem NO, eixo Y cresce para sul.
    xmin, _, _, ymax = area.bounds
    mpp = cfg["metros_por_tile"]
    tiles = bdf.copy()
    tiles.geometry = tiles.geometry.map(lambda g: affinity.affine_transform(
        g, [1/mpp, 0, 0, -1/mpp, -xmin/mpp, ymax/mpp]))
    doc = json.loads(tiles.to_json(drop_id=True))
    doc.pop("crs", None)
    doc["coordinate_system"] = "local_tiles; origin=northwest; x=east; y=south; NOT WGS84"
    # JSON local NÃO usa extensão GeoJSON: não deve ser interpretado como lon/lat.
    write_json(out / "edificios_tiles.json", doc)


def font(size: int, bold: bool = False):
    candidates = [Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size=size)


def create_preview(out: Path, classes, buildings, cfg: dict, area):
    side, left, top = 1024, 48, 160
    canvas = Image.new("RGB", (1460, 1280), "#f5f3ec")
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 32), "REGIÃO CARBONÍFERA / PZ", fill="#647268", font=font(17, True))
    draw.text((48, 65), "Centro de Criciúma", fill="#20352f", font=font(40, True))
    draw.text((48, 120), "Protótipo geográfico 01 • Praça Nereu Ramos • norte para cima", fill="#5a655d", font=font(18))
    base = Image.fromarray(PREVIEW_PALETTE[classes]).resize((side, side), Image.Resampling.NEAREST)
    # Máscara com rasterio preserva buracos nos polígonos dos edifícios.
    if buildings:
        mask = rasterize([(r["geometry"], 1) for r in buildings], out_shape=(side, side),
                         transform=from_bounds(*area.bounds, side, side), fill=0, dtype="uint8")
        base.paste((183, 139, 105), mask=Image.fromarray(mask*255))
    canvas.paste(base, (left, top))
    draw = ImageDraw.Draw(canvas)
    cells = cfg["tiles"] // cfg["tiles_por_celula"]
    for i in range(1, cells):
        offset = round(side*i/cells)
        draw.line((left+offset, top, left+offset, top+side), fill="#ffffff", width=1)
        draw.line((left, top+offset, left+side, top+offset), fill="#ffffff", width=1)
    for y in range(cells):
        for x in range(cells):
            draw.text((left+side*x/cells+10, top+side*y/cells+7), f"{x},{y}", fill="#354039", font=font(16, True))
    cx, cy = left+side//2, top+side//2
    draw.ellipse((cx-9, cy-9, cx+9, cy+9), fill="#d25136", outline="white", width=3)
    draw.rounded_rectangle((cx+17, cy-19, cx+227, cy+13), radius=4, fill="#f5f3ec")
    draw.text((cx+24, cy-16), "Praça Nereu Ramos", fill="#20352f", font=font(18, True))
    x = 1112
    draw.text((x, 170), "ESCALA DO TESTE", fill="#20352f", font=font(18, True))
    lines = [f"{cfg['tiles']} × {cfg['tiles']} tiles", f"{cfg['metros_por_tile']:g} m reais / tile",
             f"{cfg['tiles']*cfg['metros_por_tile']/1000:.3f} km de lado",
             f"{cells*cells} células de {cfg['tiles_por_celula']}", "", "LEGENDA"]
    for i, text in enumerate(lines):
        draw.text((x, 210+32*i), text, fill="#526057", font=font(19))
    labels = ["Fundo provisório", "Áreas verdes OSM", "Ruas / asfalto", "Caminhos", "Água", "Contornos OSM"]
    colors = [tuple(map(int, c)) for c in PREVIEW_PALETTE] + [(183, 139, 105)]
    for i, (label, color) in enumerate(zip(labels, colors)):
        y = 426+i*38
        draw.rectangle((x, y, x+20, y+20), fill=color)
        draw.text((x+30, y-3), label, fill="#354039", font=font(17))
    notes = ["FASE ATUAL", "Terreno e vetores reais.", "Prédios sem interiores.", "Árvores não geradas.", "", "A cobertura do OSM", "pode ser incompleta.", "", "PNG de inspeção.", "Não importar esta prévia", "como terreno no WorldEd."]
    for i, line in enumerate(notes):
        draw.text((x, 720+i*26), line, fill="#526057", font=font(16, i == 0))
    scale_px = round(300/(cfg["tiles"]*cfg["metros_por_tile"])*side)
    draw.line((left, 1220, left+scale_px, 1220), fill="#20352f", width=4)
    draw.text((left+scale_px+12, 1206), "300 m reais", fill="#20352f", font=font(18))
    draw.text((730, 1210), "© OpenStreetMap contributors • ODbL", fill="#526057", font=font(16))
    canvas.save(out / "previa.png")


def generate(cfg: dict, out: Path, *, offline=False, refresh=False) -> dict:
    area = area_for(cfg)
    frame, provenance, snapshot = fetch_features(cfg, area, offline=offline, refresh=refresh)
    classes, buildings, streets, projected, transform = build_layers(frame, cfg, area)
    if not streets:
        raise ValueError("Nenhuma rua/caminho gerado. Verifique o centro e os dados antes de continuar.")
    out.mkdir(parents=True, exist_ok=True)
    terrain = Image.fromarray(PALETTE[classes])
    veg = Image.new("RGB", terrain.size, (0, 0, 0))
    terrain.save(out / "terreno.png")
    veg.save(out / "terreno_veg.png")  # Nome associado ao terreno esperado por WorldEd.
    veg.save(out / "vegetacao.png")   # Alias legível da proposta inicial.
    np.save(out / "classes.npy", classes, allow_pickle=False)
    save_vectors(out, buildings, streets, cfg, area)
    processed = ROOT / "data/processed" / f"{snapshot.stem}_recorte.geojson"
    write_json(processed, json.loads(projected.to_json(drop_id=True, to_wgs84=True)))
    cell_dir = out / "celulas"
    cell_dir.mkdir(exist_ok=True)
    cell_size, n = cfg["tiles_por_celula"], cfg["tiles"]
    cell_files = []
    for y in range(n // cell_size):
        for x in range(n // cell_size):
            bounds = (x*cell_size, y*cell_size, (x+1)*cell_size, (y+1)*cell_size)
            name = f"centro_{x}_{y}"
            terrain.crop(bounds).save(cell_dir / f"{name}.png")
            veg.crop(bounds).save(cell_dir / f"{name}_veg.png")
            cell_files.append({"x_local": x, "y_local": y, "terreno": f"celulas/{name}.png",
                               "vegetacao": f"celulas/{name}_veg.png"})
    create_preview(out, classes, buildings, cfg, area)
    warnings = [
        "Imagens e contornos, ainda não um mod jogável ou TMX.",
        "Paleta baseada no Rules.txt citado; conferir o Rules.txt da instalação antes de importar.",
        "Compatibilidade de exportação para 42.22 ainda não validada no WorldEd/jogo.",
        "Fundo é grama provisória; ausência de edifícios no OSM não significa terreno vazio.",
        "Larguras ajustadas para jogabilidade; edifícios pequenos ainda exigem modelos.",
        "Pontes e túneis lineares omitidos: precisam de níveis e revisão manual.",
        "Caminhos e leitos de água usam superfícies/larguras provisórias.",
        "Coordenadas de células são locais; localização global no jogo ainda não definida.",
    ]
    if not buildings:
        warnings.append("Nenhum contorno de edifício retornado pelo OSM nesta área.")
    manifest = {
        "nome": cfg["nome"], "config": cfg,
        "gerado_utc": datetime.now(timezone.utc).isoformat(),
        "osm": {**provenance, "snapshot": str(snapshot.relative_to(ROOT)),
                "sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()},
        "geografia": {"crs": cfg["crs_metrico"], "bounds_utm": list(area.bounds),
                      "affine_pixel_to_utm": list(transform)[:6],
                      "lado_real_m": n*cfg["metros_por_tile"],
                      "orientacao": "origem NO; x leste; y sul; norte para cima"},
        "contagens": {"feicoes_osm_no_recorte": len(projected), "segmentos_ruas_caminhos": len(streets),
                      "poligonos_edificios": len(buildings),
                      "edificios_menores_que_16_tiles2": sum(b["area_reduzida_tiles2"] < 16 for b in buildings)},
        "classes": [{"id": i, "nome": label, "rgb": PALETTE[i].tolist(),
                     "pixels": int(np.count_nonzero(classes == i))}
                    for i, label in enumerate(["fundo_provisorio", "verde", "asfalto", "caminho", "agua"])],
        "paleta_fonte": RULES_SOURCE,
        "vegetacao": "RGB preto = sem vegetação explícita neste protótipo; não é biomemap B42",
        "celulas": cell_files,
        "versoes_python": {name: importlib.metadata.version(name) for name in
                           ("osmnx", "geopandas", "shapely", "pyproj", "rasterio", "pillow", "numpy")},
        "limitacoes": warnings,
    }
    write_json(out / "manifest.json", manifest)
    (out / "ATRIBUICAO.txt").write_text(
        "Dados geográficos: © OpenStreetMap contributors\n"
        "https://www.openstreetmap.org/copyright\n"
        "Base OpenStreetMap sob ODbL 1.0: https://opendatacommons.org/licenses/odbl/1-0/\n"
        "Dados derivados e imagens deste protótipo usam essa base. Preserve a atribuição.\n",
        encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/centro.json")
    parser.add_argument("--output", type=Path, default=ROOT / "output/centro")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="Exige snapshot local; não consulta a rede.")
    mode.add_argument("--atualizar-osm", action="store_true", help="Refaz a consulta OSM, ignorando o cache.")
    args = parser.parse_args()
    try:
        cfg = read_config(args.config)
        manifest = generate(cfg, args.output.resolve(), offline=args.offline, refresh=args.atualizar_osm)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest["contagens"], ensure_ascii=False, indent=2))
    print(f"Pronto: {args.output.resolve() / 'previa.png'}")
    print("Próxima etapa: conferir a prévia e importar uma célula no WorldEd Native256.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
