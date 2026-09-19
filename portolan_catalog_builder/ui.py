"""GUI workflow. All live QGIS objects stay on the main thread."""
import json
from pathlib import Path
from qgis.PyQt.QtCore import Qt, QTimer, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
    QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QStackedWidget, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsProjectionSelectionWidget
from .domain import CatalogPlan, LayerPlan, FieldPlan, slug, validate_plan, write_json
from .engine import BuildTask, diagnostics, start_workspace, validate_environment
from .i18n import language, tr, message
from .snapshot import check_layer, snapshot_steps, thumbnail
from .styles import extract_style
from .preview import PreviewServer

def button(text, slot):
    obj = QPushButton(tr(text))
    obj.clicked.connect(slot)
    return obj

def combo(items):
    obj = QComboBox()
    for label, value in items:
        obj.addItem(tr(label), value)
    return obj

def item(text, editable=True):
    obj = QTableWidgetItem(str(text))
    if not editable:
        obj.setFlags(obj.flags() & ~Qt.ItemIsEditable)
    return obj

def checked(value):
    obj = QTableWidgetItem()
    obj.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    obj.setCheckState(Qt.Checked if value else Qt.Unchecked)
    return obj

class BuilderDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle('Portolan Catalog Builder')
        self.resize(1120, 780)
        self.plan = CatalogPlan()
        self.active_index = None
        self.running = False
        self.cancelled = False
        self.task = None
        self.server = None
        self.workspace = None
        self.snapshot_generator = None
        self.result_root = None
        self.canvas_layer = None
        self.dirty = False
        self._populate_plan()
        outer = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        for text, slot in [('Environment', self.environment), ('Refresh layers', self.refresh_inputs), ('Load settings', self.load_settings), ('Save settings', self.save_settings)]:
            toolbar.addWidget(button(text, slot))
        toolbar.addStretch()
        self.toolbar = QWidget()
        self.toolbar.setLayout(toolbar)
        outer.addWidget(self.toolbar)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        self.make_layers()
        self.make_scope()
        self.make_metadata()
        self.make_fields()
        self.make_build()
        self.make_results()
        self.tabs.currentChanged.connect(self.tab_changed)
        self.status = QLabel(tr('Choose layers to export.'))
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        nav = QHBoxLayout()
        self.back = button('Back', lambda: self.tabs.setCurrentIndex(max(0, self.tabs.currentIndex() - 1)))
        self.next = button('Next', self.next_page)
        nav.addWidget(self.back)
        nav.addStretch()
        nav.addWidget(self.next)
        outer.addLayout(nav)
        self.refresh_layers()
        self.restore_project()

    def _populate_plan(self):
        project = QgsProject.instance()
        self.plan.title = project.title()
        seen = set()
        for n, node in enumerate(project.layerTreeRoot().findLayers(), 1):
            layer = node.layer()
            if not isinstance(layer, QgsVectorLayer):
                continue
            ident = slug(layer.name(), n)
            if ident in seen:
                ident += '-' + str(n)
            seen.add(ident)
            meta = layer.metadata()
            self.plan.layers.append(LayerPlan(layer.id(), ident, meta.title() or layer.name(),
                meta.abstract(), enabled=node.isVisible() and not check_layer(layer),
                fields=[FieldPlan(f.name(), f.name(), f.typeName(), title=f.alias(), description=f.comment()) for f in layer.fields()]))

    def refresh_inputs(self):
        if self.running:
            return
        self.save_layer()
        existing = {entry.layer_id for entry in self.plan.layers}
        ids = {entry.id for entry in self.plan.layers}
        for n, node in enumerate(QgsProject.instance().layerTreeRoot().findLayers(), 1):
            layer = node.layer()
            if not isinstance(layer, QgsVectorLayer) or layer.id() in existing:
                continue
            ident = slug(layer.name(), n)
            while ident in ids:
                ident += '-new'
            ids.add(ident)
            meta = layer.metadata()
            self.plan.layers.append(LayerPlan(layer.id(), ident, meta.title() or layer.name(), meta.abstract(),
                enabled=node.isVisible() and not check_layer(layer),
                fields=[FieldPlan(f.name(), f.name(), f.typeName(), title=f.alias(), description=f.comment()) for f in layer.fields()]))
        self.refresh_layers()

    def add_active_layer(self):
        self.refresh_inputs()
        active = self.iface.activeLayer()
        if active:
            for entry in self.plan.layers:
                if entry.layer_id == active.id() and not check_layer(active):
                    entry.enabled = True
            self.refresh_layers()

    def page(self, title):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.tabs.addTab(widget, tr(title))
        return layout

    def make_layers(self):
        layout = self.page('1 · Layers')
        layout.addWidget(QLabel(tr('Visible supported layers are selected. Background maps are not exported.')))
        self.all_tiles = QCheckBox(tr('PMTiles for selected layers'))
        self.all_tiles.setTristate(True)
        self.all_tiles.clicked.connect(self.toggle_all_tiles)
        layout.addWidget(self.all_tiles)
        self.layers = QTableWidget(0, 7)
        self.layers.setHorizontalHeaderLabels([tr(x) for x in ('Export', 'Layer', 'Collection ID', 'Features', 'CRS', 'PMTiles', 'Status')])
        self.layers.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.layers.horizontalHeader().setStretchLastSection(True)
        self.layers.itemChanged.connect(self.layer_changed)
        layout.addWidget(self.layers)

    def refresh_layers(self):
        self.layers.blockSignals(True)
        self.layers.setRowCount(len(self.plan.layers))
        for row, entry in enumerate(self.plan.layers):
            layer = QgsProject.instance().mapLayer(entry.layer_id)
            issue = check_layer(layer)
            if issue:
                entry.enabled = False
            self.layers.setItem(row, 0, checked(entry.enabled))
            if issue:
                self.layers.item(row, 0).setFlags(Qt.ItemIsEnabled)
            self.layers.setItem(row, 1, item(layer.name() if layer else entry.title, False))
            self.layers.setItem(row, 2, item(entry.id))
            self.layers.setItem(row, 3, item(layer.featureCount() if layer else '?', False))
            self.layers.setItem(row, 4, item(layer.crs().authid() if layer else '?', False))
            self.layers.setItem(row, 5, checked(entry.pmtiles))
            self.layers.setItem(row, 6, item(tr(issue) if issue else tr('Ready'), False))
        self.layers.blockSignals(False)
        self.update_all_tiles()
        self.refresh_selectors()

    def layer_changed(self, cell):
        entry = self.plan.layers[cell.row()]
        if cell.column() == 0:
            entry.enabled = cell.checkState() == Qt.Checked
        elif cell.column() == 2:
            entry.id = cell.text()
        elif cell.column() == 5:
            entry.pmtiles = cell.checkState() == Qt.Checked
        self.dirty = True
        self.update_all_tiles()
        self.refresh_selectors()

    def update_all_tiles(self):
        states = [x.pmtiles for x in self.plan.layers if x.enabled]
        state = Qt.Checked if states and all(states) else Qt.Unchecked if not any(states) else Qt.PartiallyChecked
        self.all_tiles.setCheckState(state)

    def toggle_all_tiles(self):
        enabled = self.all_tiles.checkState() != Qt.Unchecked
        for entry in self.plan.layers:
            if entry.enabled:
                entry.pmtiles = enabled
        self.refresh_layers()
        self.dirty = True

    def refresh_selectors(self):
        if not hasattr(self, 'layer_selector'):
            return
        previous = self.layer_selector.currentData()
        self.layer_selector.blockSignals(True)
        self.layer_selector.clear()
        for index, entry in enumerate(self.plan.layers):
            if entry.enabled:
                self.layer_selector.addItem(entry.title, index)
        match = self.layer_selector.findData(previous)
        self.layer_selector.setCurrentIndex(match if match >= 0 else 0)
        self.layer_selector.blockSignals(False)
        self.active_index = None
        self.select_layer()

    def make_scope(self):
        layout = self.page('2 · Selection')
        self.layer_selector = QComboBox()
        self.layer_selector.currentIndexChanged.connect(self.select_layer)
        layout.addWidget(self.layer_selector)
        layout.addWidget(QLabel(tr('This collection is also used in the Fields and map page.')))
        form = QFormLayout()
        self.scope = combo([('All features', 'all'), ('Selected features', 'selected'), ('Intersect map extent', 'extent'), ('Clip to map extent', 'clip')])
        self.scope.currentIndexChanged.connect(self.save_layer)
        form.addRow(tr('Features to export'), self.scope)
        self.extent_label = QLabel()
        form.addRow(tr('Captured extent'), self.extent_label)
        form.addRow(button('Capture current map extent', self.capture_extent))
        self.output_crs = QgsProjectionSelectionWidget()
        self.output_crs.setOptionVisible(QgsProjectionSelectionWidget.CrsNotSet, True)
        self.output_crs.crsChanged.connect(self.save_layer)
        form.addRow(tr('Output CRS (unset = source)'), self.output_crs)
        self.repair = QCheckBox(tr('Repair invalid geometry in the export copy'))
        self.skip_empty = QCheckBox(tr('Omit empty geometry and report the count'))
        self.repair.toggled.connect(self.save_layer)
        self.skip_empty.toggled.connect(self.save_layer)
        form.addRow(self.repair)
        form.addRow(self.skip_empty)
        layout.addLayout(form)
        label = QLabel(tr('Current unsaved edits, provider filters, joins and calculated values are included. Source data is never saved or modified.'))
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()

    def make_metadata(self):
        layout = self.page('3 · Catalog and descriptions')
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        self.catalog_inputs = {}
        for key, label in [('id', 'Catalog ID'), ('title', 'Title'), ('description', 'Description'),
            ('producer', 'Producer'), ('host', 'Maintainer / host'), ('contact', 'Contact (HTTPS URL or email)'),
            ('license', 'License (SPDX identifier or other)'), ('license_url', 'License URL'),
            ('source_url', 'Source URL'), ('canonical_url', 'Source STAC URL'), ('keywords', 'Keywords (comma separated)'), ('notes', 'Documentation notes')]:
            obj = QPlainTextEdit() if key in ('description', 'notes') else QLineEdit()
            if isinstance(obj, QPlainTextEdit):
                obj.setMaximumHeight(75)
            self.catalog_inputs[key] = obj
            form.addRow(tr(label), obj)
            obj.textChanged.connect(self.mark_dirty)
        self.document_language = combo([('English', 'en'), ('Japanese', 'ja')])
        form.addRow(tr('Document language'), self.document_language)
        self.document_language.currentIndexChanged.connect(self.mark_dirty)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        self.populate_catalog()

    def populate_catalog(self):
        for key, obj in self.catalog_inputs.items():
            value = getattr(self.plan, key)
            obj.setPlainText(value) if isinstance(obj, QPlainTextEdit) else obj.setText(value)
        self.document_language.setCurrentIndex(self.document_language.findData(self.plan.document_language))
        if hasattr(self, 'destination'):
            self.destination.setText(self.plan.output)

    def make_fields(self):
        layout = self.page('4 · Fields and map')
        self.active_label = QLabel()
        layout.addWidget(self.active_label)
        form = QFormLayout()
        self.layer_inputs = {}
        for key, label in [('title', 'Collection title'), ('description', 'Collection description'),
                           ('start', 'Start time (ISO 8601 or empty)'), ('end', 'End time (ISO 8601 or empty)'),
                           ('notes', 'Collection notes')]:
            obj = QLineEdit()
            self.layer_inputs[key] = obj
            obj.editingFinished.connect(self.save_layer)
            form.addRow(tr(label), obj)
        overrides = QComboBox()
        overrides.addItem(tr('Collection overrides (empty = catalog value)'))
        self.override_key = combo([(label, key) for key, label in [('producer', 'Producer'), ('host', 'Maintainer / host'),
            ('contact', 'Contact (HTTPS URL or email)'), ('license', 'License (SPDX identifier or other)'),
            ('license_url', 'License URL'), ('source_url', 'Source URL'), ('canonical_url', 'Source STAC URL'), ('keywords', 'Keywords (comma separated)')]])
        self.override_value = QLineEdit()
        self.override_value.editingFinished.connect(self.save_override)
        self.override_key.currentIndexChanged.connect(self.show_override)
        row = QHBoxLayout()
        row.addWidget(self.override_key)
        row.addWidget(self.override_value)
        form.addRow(tr('Override'), row)
        layout.addLayout(form)
        self.fields = QTableWidget(0, 9)
        self.fields.setHorizontalHeaderLabels([tr(x) for x in ('Publish', 'Source field', 'Output field', 'Type', 'Display name', 'Description', 'Unit', 'Null meaning', 'Code meanings')])
        self.fields.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.fields.itemChanged.connect(self.save_layer)
        layout.addWidget(self.fields)
        row = QHBoxLayout()
        self.tiles_enabled = QCheckBox(tr('Generate PMTiles'))
        self.tiles_enabled.toggled.connect(self.tiles_changed)
        self.make_thumbnail = QCheckBox(tr('Generate thumbnail'))
        self.make_thumbnail.toggled.connect(self.save_layer)
        row.addWidget(self.tiles_enabled)
        row.addWidget(self.make_thumbnail)
        layout.addLayout(row)
        self.tile_controls = QWidget()
        row = QHBoxLayout(self.tile_controls)
        self.autozoom = QCheckBox(tr('Recommended zoom'))
        self.minzoom, self.maxzoom = QSpinBox(), QSpinBox()
        for obj in (self.minzoom, self.maxzoom):
            obj.setRange(0, 22)
            obj.valueChanged.connect(self.save_layer)
        self.simplification = QDoubleSpinBox()
        self.simplification.setRange(0, 20)
        self.simplification.valueChanged.connect(self.save_layer)
        self.basic_style = QCheckBox(tr('Use a basic style'))
        self.basic_style.toggled.connect(self.save_layer)
        self.autozoom.toggled.connect(self.zoom_changed)
        for obj in (self.autozoom, QLabel(tr('Minimum zoom')), self.minzoom, QLabel(tr('Maximum zoom')), self.maxzoom,
                    QLabel(tr('Simplification')), self.simplification, self.basic_style):
            row.addWidget(obj)
        layout.addWidget(self.tile_controls)

    def select_layer(self, *args):
        if not hasattr(self, 'fields'):
            return
        self.save_layer()
        self.active_index = self.layer_selector.currentData()
        if self.active_index is None:
            self.fields.setRowCount(0)
            return
        entry = self.plan.layers[self.active_index]
        self.loading_layer = True
        self.active_label.setText(tr('Collection') + ': ' + entry.title + ' (' + entry.id + ')')
        self.scope.setCurrentIndex(self.scope.findData(entry.scope))
        self.extent_label.setText(str(entry.extent) + ' ' + entry.extent_crs)
        from qgis.core import QgsCoordinateReferenceSystem
        self.output_crs.setCrs(QgsCoordinateReferenceSystem(entry.output_crs))
        self.repair.setChecked(entry.repair)
        self.skip_empty.setChecked(entry.skip_empty)
        for key, obj in self.layer_inputs.items():
            obj.setText(getattr(entry, key))
        self.fields.setRowCount(len(entry.fields))
        for row, f in enumerate(entry.fields):
            self.fields.setItem(row, 0, checked(f.include))
            for col, value in enumerate((f.source, f.name, f.type, f.title, f.description, f.unit, f.null_meaning, f.codes), 1):
                self.fields.setItem(row, col, item(value, col not in (1, 3)))
        self.tiles_enabled.setChecked(entry.pmtiles)
        self.make_thumbnail.setChecked(entry.thumbnail)
        self.autozoom.setChecked(entry.autozoom)
        self.minzoom.setValue(entry.minzoom)
        self.maxzoom.setValue(entry.maxzoom)
        self.simplification.setValue(entry.simplification)
        self.basic_style.setChecked(entry.basic_style)
        self.tile_controls.setEnabled(entry.pmtiles)
        self.maxzoom.setEnabled(not entry.autozoom)
        self.show_override()
        self.loading_layer = False

    def save_layer(self, *args):
        if self.active_index is None or getattr(self, 'loading_layer', False) or not hasattr(self, 'fields'):
            return
        entry = self.plan.layers[self.active_index]
        entry.scope = self.scope.currentData()
        entry.output_crs = self.output_crs.crs().authid() or self.output_crs.crs().toWkt()
        entry.repair, entry.skip_empty = self.repair.isChecked(), self.skip_empty.isChecked()
        for key, obj in self.layer_inputs.items():
            setattr(entry, key, obj.text())
        for row, f in enumerate(entry.fields):
            if not self.fields.item(row, 8):
                continue
            f.include = self.fields.item(row, 0).checkState() == Qt.Checked
            for col, key in ((2, 'name'), (4, 'title'), (5, 'description'), (6, 'unit'), (7, 'null_meaning'), (8, 'codes')):
                setattr(f, key, self.fields.item(row, col).text())
        entry.pmtiles = self.tiles_enabled.isChecked()
        entry.thumbnail = self.make_thumbnail.isChecked()
        entry.autozoom = self.autozoom.isChecked()
        entry.minzoom, entry.maxzoom = self.minzoom.value(), self.maxzoom.value()
        entry.simplification = self.simplification.value()
        entry.basic_style = self.basic_style.isChecked()
        self.dirty = True

    def save_override(self):
        if self.active_index is not None:
            setattr(self.plan.layers[self.active_index], self.override_key.currentData(), self.override_value.text())
            self.dirty = True

    def show_override(self):
        if self.active_index is not None:
            self.override_value.setText(getattr(self.plan.layers[self.active_index], self.override_key.currentData()))

    def tiles_changed(self):
        self.tile_controls.setEnabled(self.tiles_enabled.isChecked())
        self.save_layer()
        if not getattr(self, 'loading_layer', False) and self.active_index is not None:
            self.layers.blockSignals(True)
            self.layers.item(self.active_index, 5).setCheckState(Qt.Checked if self.tiles_enabled.isChecked() else Qt.Unchecked)
            self.layers.blockSignals(False)
            self.update_all_tiles()

    def zoom_changed(self):
        self.maxzoom.setEnabled(not self.autozoom.isChecked())
        self.save_layer()

    def capture_extent(self):
        if self.active_index is None:
            return
        extent = self.iface.mapCanvas().extent()
        entry = self.plan.layers[self.active_index]
        entry.extent = [extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()]
        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        entry.extent_crs = crs.authid() or crs.toWkt()
        self.extent_label.setText(str(entry.extent) + ' ' + entry.extent_crs)
        self.dirty = True

    def mark_dirty(self):
        self.dirty = True

    def collect(self):
        self.save_layer()
        for key, obj in self.catalog_inputs.items():
            setattr(self.plan, key, obj.toPlainText() if isinstance(obj, QPlainTextEdit) else obj.text())
        self.plan.document_language = self.document_language.currentData()
        self.plan.output = self.destination.text()
        return CatalogPlan.from_dict(self.plan.to_dict())

    def make_build(self):
        layout = self.page('5 · Build')
        row = QHBoxLayout()
        self.destination = QLineEdit()
        self.destination.textChanged.connect(self.mark_dirty)
        row.addWidget(QLabel(tr('New output folder')))
        row.addWidget(self.destination)
        row.addWidget(button('Browse…', self.choose_output))
        layout.addLayout(row)
        row = QHBoxLayout()
        self.build_button = button('Build catalog', self.start_build)
        self.cancel_button = button('Cancel build', self.cancel_build)
        self.cancel_button.setEnabled(False)
        row.addWidget(self.build_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

    def choose_output(self):
        parent = QFileDialog.getExistingDirectory(self, tr('Choose parent folder'))
        if parent:
            self.destination.setText(str(Path(parent) / self.catalog_inputs['id'].text()))

    def environment(self):
        QMessageBox.information(self, tr('Environment'), json.dumps(diagnostics(), ensure_ascii=False, indent=2))

    def save_settings(self):
        plan = self.collect()
        path, _ = QFileDialog.getSaveFileName(self, tr('Save settings'), 'portolan-settings.json', 'JSON (*.json)')
        if path:
            try:
                write_json(path, plan.to_dict())
                QgsProject.instance().writeEntry('PortolanCatalogBuilder', 'plan', json.dumps(plan.to_dict(), ensure_ascii=False))
                self.dirty = False
                self.status.setText(tr('Settings saved. Save the QGIS project to retain its copy.'))
            except Exception as exc:
                self.error(exc)

    def restore_project(self):
        value, ok = QgsProject.instance().readEntry('PortolanCatalogBuilder', 'plan', '')
        if ok and value:
            try:
                self.apply_settings(CatalogPlan.from_dict(json.loads(value)))
            except Exception as exc:
                self.status.setText(tr('Saved settings could not be restored.') + ' ' + str(exc))
        self.dirty = False

    def apply_settings(self, plan):
        for entry in plan.layers:
            if QgsProject.instance().mapLayer(entry.layer_id) is None:
                from qgis.PyQt.QtWidgets import QInputDialog
                candidates = [l for l in QgsProject.instance().mapLayers().values() if isinstance(l, QgsVectorLayer)]
                names = [l.name() + ' [' + l.id() + ']' for l in candidates]
                choice, ok = QInputDialog.getItem(self, tr('Match source layer'), entry.title, names, 0, False)
                if not ok:
                    raise ValueError('Settings import cancelled; source layer is missing')
                entry.layer_id = candidates[names.index(choice)].id()
        self.active_index = None
        self.plan = plan
        self.populate_catalog()
        self.refresh_layers()

    def load_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Load settings'), '', 'JSON (*.json)')
        if path:
            try:
                self.apply_settings(CatalogPlan.from_dict(json.loads(Path(path).read_text(encoding='utf-8'))))
            except Exception as exc:
                self.error(exc)

    def tab_changed(self, index):
        if hasattr(self, 'back'):
            self.back.setEnabled(index > 0 and not self.running)
            self.next.setEnabled(index < 5 and not self.running)
        if index == 3:
            self.save_layer()
            self.select_layer()

    def next_page(self):
        self.save_layer()
        self.tabs.setCurrentIndex(min(5, self.tabs.currentIndex() + 1))

    def error(self, exc):
        QMessageBox.warning(self, tr('Cannot continue'), message(exc))

    def set_running(self, running):
        self.running = running
        self.toolbar.setEnabled(not running)
        for index in (0, 1, 2, 3, 5):
            self.tabs.setTabEnabled(index, not running)
        self.build_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.destination.setEnabled(not running)
        self.back.setEnabled(not running)
        self.next.setEnabled(not running)

    def start_build(self):
        if self.running:
            return
        try:
            self.run_plan = self.collect()
            errors = validate_plan(self.run_plan) + validate_environment(self.run_plan)
            self.run_styles = {}
            for entry in self.run_plan.layers:
                if not entry.enabled:
                    continue
                layer = QgsProject.instance().mapLayer(entry.layer_id)
                issue = check_layer(layer)
                if issue:
                    errors.append(entry.title + ': ' + tr(issue))
                elif entry.pmtiles:
                    try:
                        self.run_styles[entry.layer_id] = extract_style(layer, entry)
                    except ValueError as exc:
                        errors.append(entry.title + ': ' + str(exc))
            if errors:
                raise ValueError('\n'.join(errors))
            self.workspace = start_workspace(self.run_plan.output)
            self.run_layers = [x for x in self.run_plan.layers if x.enabled]
            self.run_index = 0
            self.run_snapshots = {}
            self.cancelled = False
            self.snapshot_generator = None
            self.log.clear()
            self.log.appendPlainText(tr('Snapshot includes current edits and evaluated attributes.'))
            self.set_running(True)
            self.progress.setRange(0, 0)
            self.snapshot_timer = QTimer(self)
            self.snapshot_timer.timeout.connect(self.snapshot_tick)
            self.snapshot_timer.start(0)
        except Exception as exc:
            self.error(exc)

    def snapshot_tick(self):
        try:
            if self.cancelled:
                raise InterruptedError(tr('Cancelled'))
            if self.run_index >= len(self.run_layers):
                self.snapshot_timer.stop()
                self.progress.setRange(0, 100)
                self.task = BuildTask(self.run_plan, self.workspace, self.run_snapshots, self.run_styles, self.build_finished)
                self.task.progressChanged.connect(lambda n: self.progress.setValue(int(n)))
                self.task.message.connect(lambda text: self.log.appendPlainText(message(text)))
                QgsApplication.taskManager().addTask(self.task)
                return
            entry = self.run_layers[self.run_index]
            if self.snapshot_generator is None:
                layer = QgsProject.instance().mapLayer(entry.layer_id)
                self.snapshot_generator = snapshot_steps(layer, entry,
                    self.workspace / 'snapshots' / (entry.id + '.gpkg'), lambda: self.cancelled)
                self.log.appendPlainText(tr('Reading layer') + ': ' + entry.title)
            result = next(self.snapshot_generator)
            if result.get('complete'):
                self.snapshot_generator.close()
                self.snapshot_generator = None
                self.run_snapshots[entry.layer_id] = result
                if entry.thumbnail:
                    self.snapshot_timer.stop()
                    layer = QgsProject.instance().mapLayer(entry.layer_id)
                    folder = self.workspace / 'catalog' / entry.id
                    folder.mkdir(exist_ok=True)
                    self.render_job, self.render_layer = thumbnail(layer, entry, result['path'], folder / 'thumbnail.png', self)
                    self.render_path = folder / 'thumbnail.png'
                    self.render_job.finished.connect(self.render_finished)
                    self.render_job.start()
                else:
                    self.run_index += 1
            else:
                self.status.setText(tr('Reading features') + ': ' + str(result['visited']))
        except Exception as exc:
            self.snapshot_timer.stop()
            if self.snapshot_generator:
                self.snapshot_generator.close()
                self.snapshot_generator = None
            self.build_finished(False, str(exc), {}, self.workspace)

    def render_finished(self):
        if getattr(self, 'shutting_down', False):
            return
        if not self.cancelled and not self.render_job.renderedImage().save(str(self.render_path), 'PNG'):
            self.build_finished(False, tr('Could not save thumbnail'), {}, self.workspace)
            return
        self.render_job = None
        self.render_layer = None
        self.run_index += 1
        self.snapshot_timer.start(0)

    def cancel_build(self):
        self.cancelled = True
        if self.task:
            self.task.cancel()
        if getattr(self, 'render_job', None):
            self.render_job.cancelWithoutBlocking()
        self.status.setText(tr('Waiting for the current operation to stop…'))

    def build_finished(self, success, error, report, workspace):
        self.set_running(False)
        self.task = None
        self.progress.setRange(0, 100)
        self.status.setText(tr('Build complete') if success else tr('Build failed or cancelled'))
        self.log.appendPlainText(self.status.text())
        self.log.appendPlainText(message(error))
        self.log.appendPlainText(tr('Build files') + ': ' + str(workspace))
        if report.get('report_folder'):
            self.log.appendPlainText(tr('Validation') + ': ' + report['report_folder'])
        self.result_root = Path(self.run_plan.output) if success else Path(workspace) / 'catalog'
        self.result_report = report
        self.findings.setRowCount(0)
        for finding in report.get('findings', []):
            row = self.findings.rowCount()
            self.findings.insertRow(row)
            for col, key in enumerate(('severity', 'rule_id', 'path', 'message')):
                self.findings.setItem(row, col, item(finding.get(key, ''), False))
        for ident, info in report.get('collections', {}).items():
            for warning in info.get('warnings', []):
                row = self.findings.rowCount()
                self.findings.insertRow(row)
                for col, value in enumerate(('warning', 'GDAL', ident + '/collection.json', warning)):
                    self.findings.setItem(row, col, item(value, False))
        self.result_status.setText((tr('Catalog created. Basic export checks completed.') if success else tr('Build failed or cancelled'))
            + f' · {report.get("error_count", "?")} ' + tr('errors') + f' · {report.get("warning_count", "?")} ' + tr('warnings')
            + '\n' + tr('Detailed validation has not been run. Before publishing or distributing, follow the Detailed validation guide.')
            + '\n' + tr('Hosting validation: not run') + '\n' + tr('Map display: review the generated output below'))
        self.result_collections.clear()
        for entry in self.run_layers:
            if (self.result_root / entry.id / 'collection.json').exists():
                self.result_collections.addItem(entry.title, entry.id)
        self.files.setPlainText('\n'.join(str(p.relative_to(self.result_root)) for p in self.result_root.rglob('*') if p.is_file()))
        if self.server:
            self.server.close()
            self.server = None
        if success:
            QgsProject.instance().writeEntry('PortolanCatalogBuilder', 'plan', json.dumps(self.run_plan.to_dict(), ensure_ascii=False))
        self.tabs.setCurrentIndex(5)
        self.show_result_collection()

    def make_results(self):
        layout = self.page('6 · Results')
        self.result_status = QLabel(tr('No catalog has been built yet.'))
        self.result_status.setWordWrap(True)
        layout.addWidget(self.result_status)
        self.validation_guide_button = button('Detailed validation guide', self.open_validation_guide)
        layout.addWidget(self.validation_guide_button)
        self.result_collections = QComboBox()
        self.result_collections.currentIndexChanged.connect(self.show_result_collection)
        layout.addWidget(self.result_collections)
        self.result_tabs = QTabWidget()
        layout.addWidget(self.result_tabs)
        self.findings = QTableWidget(0, 4)
        self.findings.setHorizontalHeaderLabels([tr(x) for x in ('Severity', 'Rule', 'File', 'Message')])
        self.findings.horizontalHeader().setStretchLastSection(True)
        self.findings.cellDoubleClicked.connect(self.finding_clicked)
        self.result_tabs.addTab(self.findings, tr('Validation'))
        map_widget = QWidget()
        map_layout = QVBoxLayout(map_widget)
        self.map_notice = QLabel()
        map_layout.addWidget(self.map_notice)
        self.open_web_button = button('Open PMTiles map', self.open_web)
        map_layout.addWidget(self.open_web_button)
        self.canvas = QgsMapCanvas()
        self.pan = QgsMapToolPan(self.canvas)
        self.canvas.setMapTool(self.pan)
        map_layout.addWidget(self.canvas)
        self.result_tabs.addTab(map_widget, tr('Map'))
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        self.attributes = QTableWidget()
        self.attributes.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table_layout.addWidget(self.attributes)
        self.page_label = QLabel()
        table_layout.addWidget(self.page_label)
        nav = QHBoxLayout()
        nav.addWidget(button('Previous page', lambda: self.load_attribute_page(-1)))
        nav.addWidget(button('Next page', lambda: self.load_attribute_page(1)))
        table_layout.addLayout(nav)
        self.result_tabs.addTab(table_widget, tr('Attributes'))
        self.docs = QPlainTextEdit()
        self.docs.setReadOnly(True)
        self.result_tabs.addTab(self.docs, tr('Documentation'))
        self.files = QPlainTextEdit()
        self.files.setReadOnly(True)
        self.result_tabs.addTab(self.files, tr('Files'))
        row = QHBoxLayout()
        row.addWidget(button('Open output folder', self.open_folder))
        row.addWidget(button('Open build report', self.open_build_report))
        row.addWidget(button('Add GeoParquet to QGIS', self.add_to_qgis))
        layout.addLayout(row)

    def open_validation_guide(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Detailed validation guide'))
        dialog.resize(780, 620)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser(dialog)
        browser.setOpenExternalLinks(True)
        path = Path(__file__).parent / 'help' / ('validation-ja.md' if language() == 'ja' else 'validation-en.md')
        browser.setMarkdown(path.read_text(encoding='utf-8'))
        layout.addWidget(browser)
        dialog.show()
        self.guide_dialog = dialog

    def open_build_report(self):
        folder = getattr(self, 'result_report', {}).get('report_folder')
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(folder) / 'build-report.json')))

    def finding_clicked(self, row, col):
        path = self.findings.item(row, 2).text().replace('\\', '/')
        for entry in self.plan.layers:
            if path.startswith(entry.id + '/'):
                for index in range(self.layer_selector.count()):
                    if self.plan.layers[self.layer_selector.itemData(index)].id == entry.id:
                        self.layer_selector.setCurrentIndex(index)
                        break
                break
        self.tabs.setCurrentIndex(3)

    def show_result_collection(self):
        ident = self.result_collections.currentData()
        if not self.result_root or not ident:
            return
        folder = self.result_root / ident
        try:
            collection = json.loads((folder / 'collection.json').read_text(encoding='utf-8'))
            self.current_data_path = folder / (ident + '.parquet')
            self.canvas.setLayers([])
            self.canvas_layer = QgsVectorLayer(str(self.current_data_path), collection['title'], 'ogr')
            if self.canvas_layer.isValid():
                self.canvas.setDestinationCrs(self.canvas_layer.crs())
                self.canvas.setLayers([self.canvas_layer])
                extent = self.canvas_layer.extent()
                if extent.width() == 0 or extent.height() == 0:
                    extent.grow(0.01 if self.canvas_layer.crs().isGeographic() else 100)
                extent.scale(1.15)
                self.canvas.setExtent(extent)
                self.canvas.refresh()
            tiles = any(x['rel'] == 'pmtiles' for x in collection['links'])
            self.open_web_button.setEnabled(tiles)
            self.map_notice.setText(tr('GeoParquet preview. Use the button to inspect the actual PMTiles style.') if tiles else tr('GeoParquet preview (PMTiles was not requested).'))
            self.docs.setPlainText((folder / 'README.md').read_text(encoding='utf-8') + '\n\n' + (folder / 'AGENTS.md').read_text(encoding='utf-8'))
            self.attribute_page = 0
            self.load_attribute_page(0)
        except Exception as exc:
            self.result_status.setText(str(exc))

    def load_attribute_page(self, delta):
        if not hasattr(self, 'current_data_path'):
            return
        from osgeo import ogr
        source = ogr.Open(str(self.current_data_path))
        if source is None:
            return
        layer = source.GetLayer(0)
        total = layer.GetFeatureCount()
        page = max(0, min((total - 1) // 100, self.attribute_page + delta))
        self.attribute_page = page
        layer.SetNextByIndex(page * 100)
        names = [f.GetName() for f in layer.schema]
        self.attributes.setColumnCount(len(names))
        self.attributes.setHorizontalHeaderLabels(names)
        self.attributes.setRowCount(0)
        for n in range(100):
            feature = layer.GetNextFeature()
            if feature is None:
                break
            self.attributes.insertRow(n)
            for col in range(len(names)):
                value = feature.GetField(col)
                self.attributes.setItem(n, col, item('NULL' if value is None else value, False))
        self.page_label.setText(tr('Rows') + f' {page * 100 + 1}–{page * 100 + self.attributes.rowCount()} / {total}')
        source = None

    def open_web(self):
        ident = self.result_collections.currentData()
        if ident and self.result_root:
            if self.server is None:
                self.server = PreviewServer(self.result_root)
            QDesktopServices.openUrl(QUrl(self.server.url(ident, language())))

    def open_folder(self):
        if self.result_root:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.result_root)))

    def add_to_qgis(self):
        if hasattr(self, 'current_data_path'):
            self.iface.addVectorLayer(str(self.current_data_path), self.result_collections.currentText(), 'ogr')

    def closeEvent(self, event):
        if self.running:
            self.status.setText(tr('Cancel the build before closing this window.'))
            event.ignore()
        elif self.dirty:
            answer = QMessageBox.question(self, tr('Unsaved settings'), tr('Close without saving settings?'))
            if answer == QMessageBox.Yes:
                self.dirty = False
                if self.server:
                    self.server.close()
                    self.server = None
                event.accept()
            else:
                event.ignore()
        else:
            if self.server:
                self.server.close()
                self.server = None
            event.accept()

    def shutdown(self):
        self.shutting_down = True
        self.cancelled = True
        if hasattr(self, 'snapshot_timer'):
            self.snapshot_timer.stop()
        if self.snapshot_generator:
            self.snapshot_generator.close()
            self.snapshot_generator = None
        if getattr(self, 'render_job', None):
            self.render_job.cancel()
        if self.task:
            self.task.callback = lambda *args: None
            self.task.cancel()
            self.task.waitForFinished()
        if self.server:
            self.server.close()
            self.server = None
        self.running = False
        self.dirty = False
