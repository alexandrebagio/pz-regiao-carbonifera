"""Casos espaciais que não dependem da rede nem de dados reais do OSM."""
import json
from pathlib import Path
import tempfile
import unittest

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Polygon, box, shape

from scripts.gerar_centro import build_layers, save_vectors


class GeographyTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"tiles": 32, "metros_por_tile": 3, "crs_metrico": "EPSG:32722",
                    "largura_minima_rua_tiles": 8, "largura_minima_caminho_tiles": 2}
        self.area = box(650000, 6800000, 650096, 6800096)

    def frame(self, records):
        return gpd.GeoDataFrame(records, geometry="geometry", crs=self.cfg["crs_metrico"])

    def test_narrow_real_road_has_eight_tiles_for_two_cars(self):
        frame = self.frame([{"highway": "residential", "width": "3", "geometry":
                             LineString([(649980, 6800048), (650120, 6800048)])}])
        classes, _, _, _, _ = build_layers(frame, self.cfg, self.area)
        rows = np.flatnonzero(classes[:, 16] == 2)
        self.assertEqual(rows.tolist(), list(range(12, 20)))
        self.assertTrue(np.all(classes[12:20, :] == 2))

    def test_road_outside_centerline_still_paints_map_edge(self):
        frame = self.frame([{"highway": "residential", "geometry":
                             LineString([(649997, 6799980), (649997, 6800120)])}])
        classes, _, _, _, _ = build_layers(frame, self.cfg, self.area)
        self.assertTrue(np.all(classes[:, 0] == 2))
        self.assertTrue(np.all(classes[:, 4:] == 0))

    def test_green_polygon_preserves_hole_and_north_orientation(self):
        geom = Polygon([(650006, 6800054), (650042, 6800054), (650042, 6800090), (650006, 6800090)],
                       holes=[[(650015, 6800063), (650033, 6800063), (650033, 6800081), (650015, 6800081)]])
        classes, _, _, _, _ = build_layers(self.frame([{"leisure": "park", "geometry": geom}]), self.cfg, self.area)
        self.assertEqual(classes[3, 3], 1)
        self.assertEqual(classes[7, 7], 0)  # buraco
        self.assertTrue(np.all(classes[16:, :] == 0))  # parque está ao norte

    def test_building_clipped_and_transformed_to_local_tiles(self):
        frame = self.frame([{"building": "yes", "geometry": box(649990, 6800084, 650012, 6800110)}])
        _, buildings, streets, _, _ = build_layers(frame, self.cfg, self.area)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            save_vectors(out, buildings, streets, self.cfg, self.area)
            local = json.loads((out / "edificios_tiles.json").read_text(encoding="utf-8"))
            bounds = shape(local["features"][0]["geometry"]).bounds
            np.testing.assert_allclose(bounds, (0, 0, 4, 4), atol=1e-7)
            self.assertNotIn("crs", local)

    def test_bridge_tunnel_and_traffic_signal_are_not_ground_roads(self):
        line = LineString([(650000, 6800048), (650096, 6800048)])
        frame = self.frame([{"highway": "residential", "bridge": "yes", "geometry": line},
                            {"highway": "residential", "tunnel": "yes", "geometry": line},
                            {"highway": "traffic_signals", "geometry": line.centroid}])
        classes, _, roads, _, _ = build_layers(frame, self.cfg, self.area)
        self.assertFalse(np.any(classes))
        self.assertEqual(roads, [])


if __name__ == "__main__":
    unittest.main()
