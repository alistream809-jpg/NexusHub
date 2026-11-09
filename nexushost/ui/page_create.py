import psutil
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLineEdit, QSlider, QSpinBox

from ..core import netutil
from ..core.provisioner import CreateSpec, ValidationError, validate
from ..core.providers import PROVIDERS
from .tasks import TaskDialog
from .widgets import Card, Page, button, confirm, hbox, label, show_error, show_info, vbox


class VersionLoader(QThread):
    loaded = Signal(str, list)
    failed = Signal(str, str)

    def __init__(self, software):
        super().__init__()
        self.software = software

    def run(self):
        try:
            self.loaded.emit(self.software, PROVIDERS[self.software].versions())
        except Exception as exc:
            self.failed.emit(self.software, str(exc))


class CreatePage(Page):
    title = "Create Server"

    def __init__(self, ctx):
        super().__init__(ctx)
        self._cache = {}
        self._loaders = []
        root = vbox((28, 24, 28, 24), 16)
        self.setLayout(root)
        root.addWidget(label("Create a new Minecraft Java server", "H1"))
        root.addWidget(label("The server is downloaded from its official source and installed on this computer.", "Muted"))

        card = Card()
        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        card.box.addLayout(form)

        self.name = QLineEdit()
        self.name.setPlaceholderText("My Survival World")
        self.name.setMaxLength(40)
        form.addRow("Server name", self.name)

        self.software = QComboBox()
        self.software.addItems(list(PROVIDERS))
        self.software.currentTextChanged.connect(self._software_changed)
        form.addRow("Software", self.software)
        self.software_note = label("", "Muted", wrap=True)
        form.addRow("", self.software_note)

        ver = hbox()
        self.version = QComboBox()
        self.version.setMinimumWidth(220)
        self.reload = button("Reload", "ghost")
        self.reload.clicked.connect(lambda: self._load_versions(force=True))
        ver.addWidget(self.version)
        ver.addWidget(self.reload)
        ver.addStretch(1)
        form.addRow("Minecraft version", ver)
        self.version_note = label("", "Muted", wrap=True)
        form.addRow("", self.version_note)

        total_mb = psutil.virtual_memory().total // (1024 * 1024)
        self.max_ram = max(2048, (int(total_mb * 0.85) // 256) * 256)
        default_ram = min(4096, max(1024, (total_mb // 4 // 256) * 256))
        ram = hbox(12)
        self.ram_slider = QSlider(Qt.Orientation.Horizontal)
        self.ram_slider.setRange(1024, self.max_ram)
        self.ram_slider.setSingleStep(256)
        self.ram_slider.setPageStep(1024)
        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(1024, self.max_ram)
        self.ram_spin.setSingleStep(256)
        self.ram_spin.setSuffix(" MB")
        self.ram_spin.setMinimumWidth(120)
        self.ram_slider.valueChanged.connect(lambda v: self.ram_spin.setValue(round(v / 256) * 256))
        self.ram_spin.valueChanged.connect(self.ram_slider.setValue)
        self.ram_spin.setValue(default_ram)
        ram.addWidget(self.ram_slider, 1)
        ram.addWidget(self.ram_spin)
        form.addRow("RAM allocation", ram)
        form.addRow("", label(f"This computer has {total_mb / 1024:.1f} GB of RAM. Leave at least 2 GB for Windows and other programs.", "Muted", wrap=True))

        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(self._free_port())
        form.addRow("Port", self.port)

        self.eula = QCheckBox("I have read and accept the Minecraft EULA")
        form.addRow("", self.eula)
        eula_link = label('<a style="color:#22c55e" href="https://aka.ms/MinecraftEULA">https://aka.ms/MinecraftEULA</a>', "Muted")
        eula_link.setOpenExternalLinks(True)
        form.addRow("", eula_link)
        root.addWidget(card)

        row = hbox()
        row.addStretch(1)
        self.create_btn = button("Create Server", "primary")
        self.create_btn.setMinimumWidth(170)
        self.create_btn.clicked.connect(self._create)
        row.addWidget(self.create_btn)
        root.addLayout(row)
        root.addStretch(1)
        self._software_changed(self.software.currentText())

    def on_show(self):
        self.port.setValue(self._free_port())

    def _free_port(self) -> int:
        used = {h.record.port for h in self.ctx.handles.values()}
        port = 25565
        while port in used or not netutil.port_available(port):
            port += 1
        return port

    def _software_changed(self, name: str):
        provider = PROVIDERS[name]
        extra = {
            "Spigot": " Needs a JDK, which NEXUS HOST downloads automatically if missing.",
            "Forge": " Installation downloads libraries and may take a few minutes.",
            "Fabric": " Most mods also require the Fabric API mod.",
        }.get(name, "")
        self.software_note.setText(provider.description + extra)
        self._load_versions()

    def _load_versions(self, force=False):
        name = self.software.currentText()
        if force:
            self._cache.pop(name, None)
        if name in self._cache:
            self._fill(name, self._cache[name])
            return
        self.version.clear()
        self.version.setEnabled(False)
        self.reload.setEnabled(False)
        self.version_note.setText("Loading available versions...")
        loader = VersionLoader(name)
        loader.loaded.connect(self._loaded)
        loader.failed.connect(self._load_failed)
        loader.finished.connect(lambda ld=loader: self._loaders.remove(ld) if ld in self._loaders else None)
        self._loaders.append(loader)  # keep a reference until the thread has finished
        loader.start()

    def _loaded(self, name, versions):
        self._cache[name] = versions
        if name == self.software.currentText():
            self._fill(name, versions)

    def _fill(self, name, versions):
        self.version.clear()
        self.version.addItems(versions)
        self.version.setEnabled(bool(versions))
        self.reload.setEnabled(True)
        self.version_note.setText(f"{len(versions)} versions available." if versions else "No versions were found.")

    def _load_failed(self, name, error):
        if name == self.software.currentText():
            self.reload.setEnabled(True)
            self.version_note.setText(f"Could not load versions: {error}")

    def _create(self):
        spec = CreateSpec(self.name.text(), self.software.currentText(), self.version.currentText(),
                          self.ram_spin.value(), self.port.value(), self.eula.isChecked())
        try:
            validate(spec, self.ctx.manager.db)
        except ValidationError as exc:
            show_error(self, str(exc))
            return
        if not netutil.port_available(spec.port) and not confirm(
                self, f"Port {spec.port} is currently used by another program. Create the server anyway?"):
            return
        mgr = self.ctx.manager
        controller, error = TaskDialog(self, f"Creating {spec.name.strip()}", lambda rep: mgr.create(spec, rep)).run()
        if controller is None:
            if error and error != "Cancelled.":
                show_error(self, error, "Server creation failed")
            return
        self.ctx.add_controller(controller)
        self.name.clear()
        self.eula.setChecked(False)
        self.ctx.navigate("dashboard")
        show_info(self, f"'{spec.name.strip()}' is ready. Press Start on the dashboard to launch it.")
