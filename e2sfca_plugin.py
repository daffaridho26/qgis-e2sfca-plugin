import os.path
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .e2sfca_plugin_dialog import E2SFCAPluginDialog


class E2SFCAPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = '&E2SFCA Plugin'
        self.dlg = None

    def initGui(self):
        """Menambahkan ikon plugin ke Toolbar dan Menu Vector QGIS"""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.action = QAction(
            QIcon(icon_path),
            'E2SFCA Accessibility Calculator',
            self.iface.mainWindow(),
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu(self.menu, self.action)
        self.iface.addToolBarIcon(self.action)
        self.actions.append(self.action)

    def unload(self):
        """Menghapus ikon plugin saat di-unmount"""
        for action in self.actions:
            self.iface.removePluginVectorMenu('&E2SFCA Plugin', action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Dijalankan saat ikon plugin diklik"""
        if self.dlg is None:
            self.dlg = E2SFCAPluginDialog(self.iface)

        # Perbarui daftar layer di QGIS saat dialog dibuka
        self.dlg.populate_layers()

        # Tampilkan jendela plugin tanpa mengunci canvas peta
        self.dlg.show()
        self.dlg.activateWindow()
