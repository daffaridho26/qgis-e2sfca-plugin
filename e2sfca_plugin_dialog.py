import csv 
import math
import os
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.analysis import (
    QgsVectorLayerDirector,
    QgsNetworkDistanceStrategy,
    QgsGraphBuilder,
    QgsGraphAnalyzer,
)
import csv
FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), 'e2sfca_plugin_dialog_base.ui')
)


class E2SFCAPluginDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, iface=None, parent=None):
        super(E2SFCAPluginDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface

        # 1. Atur Judul Window
        self.setWindowTitle("E2SFCA Accessibility Calculator")

        # 2. Buka batas maksimal threshold (supaya bisa isi ribuan meter untuk mode jarak)
        self.spin_threshold.setRange(1, 999999)

        # 3. Muat Layer awal
        self.populate_layers()
        # 4. Hubungkan Event perubahan Layer ke Dropdown Atribut
        self.combo_facility_layer.currentIndexChanged.connect(
            self.populate_facility_fields
        )
        self.combo_pop_layer.currentIndexChanged.connect(
            self.populate_pop_fields
        )
        self.combo_road_layer.currentIndexChanged.connect(
            self.populate_road_fields
        )

        # 5. Hubungkan Tombol Run dan Cancel
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_run.clicked.connect(self.run_analysis)

    def populate_layers(self):
        """Membaca semua layer yang terbuka di QGIS"""
        self.combo_facility_layer.clear()
        self.combo_pop_layer.clear()
        self.combo_road_layer.clear()

        layers = QgsProject.instance().mapLayers().values()

        for layer in layers:
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                geom = layer.geometryType()

                if geom == QgsWkbTypes.PointGeometry:
                    self.combo_facility_layer.addItem(layer.name(), layer)

                if geom in [
                    QgsWkbTypes.PointGeometry,
                    QgsWkbTypes.PolygonGeometry,
                ]:
                    self.combo_pop_layer.addItem(layer.name(), layer)

                elif geom == QgsWkbTypes.LineGeometry:
                    self.combo_road_layer.addItem(layer.name(), layer)

        self.populate_facility_fields()
        self.populate_pop_fields()
        self.populate_road_fields()

    def populate_facility_fields(self):
        """Memuat kolom angka dari layer Fasilitas/RS"""
        self.combo_capacity_field.clear()
        layer = self.combo_facility_layer.currentData()
        if layer:
            for field in layer.fields():
                if field.isNumeric():
                    self.combo_capacity_field.addItem(field.name())

    def populate_pop_fields(self):
        """Memuat kolom angka dari layer Populasi"""
        self.combo_pop_field.clear()
        layer = self.combo_pop_layer.currentData()
        if layer:
            for field in layer.fields():
                if field.isNumeric():
                    self.combo_pop_field.addItem(field.name())

    def populate_road_fields(self):
        """Memuat kolom angka dari layer Jalan"""
        self.combo_speed_field.clear()
        layer = self.combo_road_layer.currentData()
        if layer:
            for field in layer.fields():
                if field.isNumeric():
                    self.combo_speed_field.addItem(field.name())

    def gaussian_decay(self, d, d0):
        """Kalkulasi Bobot Peluruhan Gaussian W_r"""
        if d > d0 or d0 <= 0:
            return 0.0
        num = math.exp(-0.5 * (d / d0) ** 2) - math.exp(-0.5)
        den = 1.0 - math.exp(-0.5)
        return max(0.0, num / den)

    def get_network_travel_times(self, road_layer, speed_field, facilities, populations, is_travel_time=True):
        """Membangun Graph Jaringan Jalan & Menghitung Waktu Tempuh (Menit) atau Jarak (Meter) via PyQGIS 3"""
        director = QgsVectorLayerDirector(road_layer, -1, '', '', '', QgsVectorLayerDirector.DirectionBoth)
        strategy = QgsNetworkDistanceStrategy()
        director.addStrategy(strategy)

        builder = QgsGraphBuilder(road_layer.crs())
        director.makeGraph(builder, [])
        graph = builder.graph()

        is_geo = road_layer.crs().isGeographic()

        # Ekstraksi titik yang aman untuk Point, MultiPoint, maupun Polygon
        def get_safe_point(geom):
            if not geom or geom.isEmpty():
                return None
            if geom.type() == QgsWkbTypes.PolygonGeometry:
                return geom.centroid().asPoint()
            elif geom.type() == QgsWkbTypes.PointGeometry:
                if geom.isMultipart():
                    pts = geom.asMultiPoint()
                    return pts[0] if pts else None
                return geom.asPoint()
            else:
                return geom.centroid().asPoint()

        travel_time_matrix = {}
        for f in facilities:
            f_geom = f.geometry()
            f_point = get_safe_point(f_geom)
            f_vertex_id = graph.findVertex(f_point) if f_point else -1

            if 0 <= f_vertex_id < graph.vertexCount():
                tree, cost = QgsGraphAnalyzer.dijkstra(graph, f_vertex_id, 0)
            else:
                tree, cost = [], []

            travel_time_matrix[f.id()] = {}
            for p in populations:
                p_geom = p.geometry()
                p_point = get_safe_point(p_geom)
                p_vertex_id = graph.findVertex(p_point) if p_point else -1

                if 0 <= p_vertex_id < len(cost) and len(cost) > 0 and cost[p_vertex_id] != float('inf'):
                    raw_cost = cost[p_vertex_id]
                    
                    # --- KONVERSI DERAJAT KE METER JIKA CRS GEOGRAPHIC ---
                    dist_m = raw_cost * 111320.0 if is_geo else raw_cost

                    if is_travel_time:
                        # Mode Travel Time: Meter dikonversi ke Menit
                        travel_time_matrix[f.id()][p.id()] = dist_m / 500.0
                    else:
                        # Mode Network Distance: Dalam Meter
                        travel_time_matrix[f.id()][p.id()] = dist_m
                else:
                    if f_geom and p_geom:
                        dist = f_geom.distance(p_geom) * (111320.0 if is_geo else 1.0)
                        
                        # --- PERBAIKAN FALLBACK DI SINI ---
                        if is_travel_time:
                            travel_time_matrix[f.id()][p.id()] = dist / 500.0
                        else:
                            travel_time_matrix[f.id()][p.id()] = dist
                    else:
                        travel_time_matrix[f.id()][p.id()] = 999999.0

        return travel_time_matrix

    def run_analysis(self):
        """Fungsi Utama Kalkulasi E2SFCA Berbasis Jaringan Jalan"""

        facility_layer = self.combo_facility_layer.currentData()
        pop_layer = self.combo_pop_layer.currentData()
        road_layer = self.combo_road_layer.currentData()

        if not facility_layer or not pop_layer or not road_layer:
            QtWidgets.QMessageBox.warning(
                self,
                "Peringatan",
                "Harap pastikan semua layer input (Fasilitas, Populasi, dan Jalan) sudah dipilih!",
            )
            return

        cap_field = self.combo_capacity_field.currentText()
        pop_field = self.combo_pop_field.currentText()
        speed_field = self.combo_speed_field.currentText()
        d0 = self.spin_threshold.value()

        if not cap_field or not pop_field:
            QtWidgets.QMessageBox.warning(
                self,
                "Peringatan",
                "Pilih kolom Kapasitas dan Populasi terlebih dahulu!",
            )
            return

        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(0)

        facilities = list(facility_layer.getFeatures())
        populations = list(pop_layer.getFeatures())

        total_steps = len(facilities) + len(populations)
        current_step = 0

        # 1. Ambil nilai threshold dan status radio button
        d0 = self.spin_threshold.value()
        
        # Menggunakan nama object radio_time dari skrip asli kamu
        is_travel_time = self.radio_time.isChecked()

        # 2. Panggil fungsi matriks jaringan dengan menyertakan is_travel_time
        travel_matrix = self.get_network_travel_times(
            road_layer, speed_field, facilities, populations, is_travel_time
        )
        
        # SIMPAN MATRIKS WAKTU TEMPUH KE CSV (Aman & Auto-Flush)
        try:
            user_home = os.path.expanduser('~')
            onedrive_desktop = os.path.join(user_home, 'OneDrive', 'Desktop')
            normal_desktop = os.path.join(user_home, 'Desktop')
            target_dir = onedrive_desktop if os.path.exists(onedrive_desktop) else (normal_desktop if os.path.exists(normal_desktop) else user_home)
            csv_path = os.path.join(target_dir, 'matriks_waktu_tempuh.csv')

            count = 0
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID_Fasilitas', 'ID_Populasi', 'Waktu_Tempuh_Menit'])
                for f_id, pops in travel_matrix.items():
                    for p_id, t_val in pops.items():
                        writer.writerow([f_id, p_id, round(t_val, 4)])
                        count += 1
                f.flush()
            print(f"[E2SFCA] Berhasil menulis {count} baris matriks ke: {csv_path}")
        except Exception as e:
            print(f"[E2SFCA] Gagal simpan CSV: {e}")
        R_j = {}

        # LANGKAH 1: Rasio Penawaran Fasilitas (R_j)
        for f in facilities:
            S_j = float(f[cap_field] or 0)
            weighted_pop_sum = 0.0

            for p in populations:
                impedance = travel_matrix[f.id()][p.id()]

                if impedance <= d0:
                    W_k = self.gaussian_decay(impedance, d0)
                    P_k = float(p[pop_field] or 0)
                    weighted_pop_sum += P_k * W_k

            R_j[f.id()] = (S_j / weighted_pop_sum) if weighted_pop_sum > 0 else 0.0

            current_step += 1
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setValue(
                    int((current_step / total_steps) * 100))

        # LANGKAH 2: Indeks Aksesibilitas (A_i)
        output_layer = QgsVectorLayer(
            f"{QgsWkbTypes.displayString(pop_layer.wkbType())}?crs={pop_layer.crs().authid()}",
            "Hasil_E2SFCA_Aksesibilitas",
            "memory",
        )
        provider = output_layer.dataProvider()

        provider.addAttributes(pop_layer.fields())
        provider.addAttributes(
            [QgsField("SAI_E2SFCA", QVariant.Double, "double", 10, 6)]
        )
        output_layer.updateFields()

        out_features = []
        for p in populations:
            A_i = 0.0

            for f in facilities:
                impedance = travel_matrix[f.id()][p.id()]

                if impedance <= d0:
                    W_ij = self.gaussian_decay(impedance, d0)
                    A_i += (R_j[f.id()] * W_ij)

            out_feat = QgsFeature()
            out_feat.setGeometry(p.geometry())
            attrs = p.attributes() + [round(A_i, 6)]
            out_feat.setAttributes(attrs)
            out_features.append(out_feat)

            current_step += 1
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setValue(
                    int((current_step / total_steps) * 100))

        provider.addFeatures(out_features)
        output_layer.updateExtents()

        # LANGKAH 3: Output & Auto-Load
        file_path = self.output_file_widget.filePath() if hasattr(self, 'output_file_widget') else None
        if file_path:
            QgsVectorFileWriter.writeAsVectorFormat(
                output_layer, file_path, "UTF-8", pop_layer.crs(), "GPKG"
            )

        auto_load = (
            self.chk_autoload.isChecked()
            if hasattr(self, 'chk_autoload')
            else True
        )
        if auto_load:
            QgsProject.instance().addMapLayer(output_layer)

        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(100)

        QtWidgets.QMessageBox.information(
            self,
            "Selesai!",
            "Analisis Aksesibilitas E2SFCA Berbasis Jaringan Jalan Berhasil!\n"
            "Layer hasil telah ditambahkan ke Canvas QGIS dengan atribut 'SAI_E2SFCA'.",
        )
        import csv
