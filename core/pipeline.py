"""
e2sfca.py
---------
Integration of the whole E2SFCA calculation:

    1. Input & CRS validation          (utils.py)
    2. Polygon/point -> point           (utils.py)
    3. Road network OD cost matrix      (cost_matrix.py)
    4. E2SFCA steps 1 & 2               (e2sfca.py)
    5. Write the output layer to file   (pipeline.py)
"""

import time
from dataclasses import dataclass, fields

from qgis.core import Qgis, QgsMessageLog, QgsVectorLayer


@dataclass
class E2SFCAParams:
    facility_layer: object
    capacity_field: str
    population_layer: object
    population_field: str
    road_layer: object
    is_travel_time: bool = False
    direction_field: str = ""
    forward_value: str = ""
    backward_value: str = ""
    both_value: str = ""
    speed_field: str = ""
    default_speed: float = 30.0
    decay_function: str = ""
    beta: float = 3.0
    cutoff: float = 0.0
    point_method: str = ""
    output_path: str = ""


def run_e2sfca(params, feedback=None):
    pass