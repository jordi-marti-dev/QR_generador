#!/usr/bin/env python3
"""
QR Code Generator — Graphical User Interface (PySide6)

Requires:
    pip install "qrcode[pil]" PySide6

Launch:
    python QR_GENERADOR_GUI.py
"""

import datetime
import json
import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QColorDialog,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from QR_GENERADOR import _validate_config, _safe_filename, generate

# Mapa entre el text que veu l'usuari i la lletra que usa la llibreria qrcode
_EC_DISPLAY_TO_KEY = {
    "H — 30 % (Alta, recomanat)": "H",
    "Q — 25 %": "Q",
    "M — 15 %": "M",
    "L — 7 % (Baixa)": "L",
}
_EC_KEY_TO_DISPLAY = {v: k for k, v in _EC_DISPLAY_TO_KEY.items()}

__version__ = "1.0.0"
_AUTHOR     = "Jordi Martí"
_EMAIL      = "jordi.marti.dev@gmail.com"
_WEB        = "https://jordimarti.dev"
_GITHUB     = "https://github.com/jordi-marti-dev/QR_generador"


# ---------------------------------------------------------------------------
# _QTextEditHandler: envia els missatges de log al panell visual de la GUI
# ---------------------------------------------------------------------------

class _QTextEditHandler(logging.Handler):
    """Handler de logging que escriu missatges en color HTML dins un QTextEdit."""

    # Colors HTML associats a cada nivell de log
    _COLORS = {
        logging.ERROR:   "#e74c3c",   # vermell
        logging.WARNING: "#e67e22",   # taronja
        logging.INFO:    "#ecf0f1",   # blanc trencat
        logging.DEBUG:   "#95a5a6",   # gris
    }

    def __init__(self, widget: QTextEdit) -> None:
        """Inicialitza el handler guardant la referència al widget de text."""
        super().__init__()
        self._widget = widget

    def emit(self, record: logging.LogRecord) -> None:
        """Formata el missatge i l'afegeix al QTextEdit amb el color del seu nivell."""
        msg = self.format(record).replace("&", "&amp;").replace("<", "&lt;")
        color = self._COLORS.get(record.levelno, "#ecf0f1")
        self._widget.append(f'<span style="color:{color};font-family:Consolas,monospace">{msg}</span>')


# ---------------------------------------------------------------------------
# ColorButton: botó que mostra el color actual i obre el selector de color
# ---------------------------------------------------------------------------

class ColorButton(QPushButton):
    """Botó QPushButton ampliat que mostra el color seleccionat i permet canviar-lo."""

    def __init__(self, initial: str = "#000000") -> None:
        """Crea el botó amb el color inicial i connecta el clic al selector."""
        super().__init__()
        self._color = QColor(initial)
        self._refresh()
        self.clicked.connect(self._pick)
        self.setFixedWidth(110)

    def _pick(self) -> None:
        """Obre el diàleg natiu de selecció de color i aplica el nou color si es confirma."""
        c = QColorDialog.getColor(self._color, self, "Tria un color")
        if c.isValid():
            self._color = c
            self._refresh()

    def _refresh(self) -> None:
        """Actualitza el fons i el text del botó perquè reflecteixi el color actual."""
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        text_col = "#000" if (0.299 * r + 0.587 * g + 0.114 * b) > 128 else "#fff"
        self.setStyleSheet(
            f"background-color:{self._color.name()}; color:{text_col};"
            "border:1px solid #666; border-radius:3px; padding:3px 8px;"
        )
        self.setText(self._color.name().upper())

    def color_hex(self) -> str:
        """Retorna el color actual com a string hexadecimal (ex: '#ff0000')."""
        return self._color.name()

    def set_color(self, value: str) -> None:
        """Canvia el color a partir d'un string CSS (nom o hex). Ignora valors invàlids."""
        c = QColor(value)
        if c.isValid():
            self._color = c
            self._refresh()


# ---------------------------------------------------------------------------
# CollapsibleBox: panell amb capçalera clicable que es pot plegar i desplegar
# ---------------------------------------------------------------------------

class CollapsibleBox(QWidget):
    """Widget amb títol clicable que amaga o mostra el seu contingut interior."""

    def __init__(self, title: str, parent=None) -> None:
        """Construeix la capçalera (QToolButton) i el contenidor de contingut."""
        super().__init__(parent)

        self._btn = QToolButton()
        self._btn.setText(f"  {title}")
        self._btn.setCheckable(True)
        self._btn.setChecked(True)
        self._btn.setArrowType(Qt.DownArrow)
        self._btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn.setStyleSheet(
            "QToolButton { text-align:left; font-weight:bold; color:white;"
            " border:1px solid #444; border-radius:3px;"
            " background:#5a5a5a; padding:5px 8px; }"
            "QToolButton:hover { background:#484848; }"
        )
        self._btn.toggled.connect(self._on_toggled)

        self._content = QWidget()

        vbox = QVBoxLayout(self)
        vbox.setSpacing(2)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(self._btn)
        vbox.addWidget(self._content)

    def _on_toggled(self, checked: bool) -> None:
        """Canvia la fletxa de la capçalera i amaga/mostra el contingut."""
        self._btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self._content.setVisible(checked)

    def set_content_layout(self, layout) -> None:
        """Assigna un layout al contenidor interior del panell."""
        self._content.setLayout(layout)


# ---------------------------------------------------------------------------
# MainWindow: finestra principal de l'aplicació
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Finestra principal que agrupa tots els panells i gestiona la interacció."""

    def __init__(self) -> None:
        """Construeix la finestra: menú, layout vertical i tots els panells."""
        super().__init__()
        self.setWindowTitle("QR Code Generator")
        self.setMinimumSize(680, 700)
        self._build_menu()

        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        main_layout = QVBoxLayout(root_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Fila superior: Configuració QR + Directori de sortida, costat a costat
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(self._build_config_group(), stretch=1, alignment=Qt.AlignTop)
        top_row.addWidget(self._build_output_group(), stretch=1, alignment=Qt.AlignTop)
        main_layout.addLayout(top_row)

        # Llista d'URLs (prou alta per veure almenys 3 files sense scroll)
        main_layout.addWidget(self._build_url_group(), stretch=1)

        # Botons d'acció sempre visibles, abans del log
        main_layout.addLayout(self._build_action_row())

        # Miniatures dels QRs generats (scroll horitzontal)
        main_layout.addWidget(self._build_preview_group())

        # Registre d'execució al final de tot (alçada reduïda)
        main_layout.addWidget(self._build_log_group())

        self._init_logging()

    # ------------------------------------------------------------------
    # UI builders — mètodes que construeixen cada panell de la finestra
    # ------------------------------------------------------------------

    def _build_config_group(self) -> CollapsibleBox:
        """Crea el panell plegable amb els paràmetres visuals del codi QR."""
        box = CollapsibleBox("Configuració del codi QR")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(16)
        form.setContentsMargins(8, 8, 8, 8)

        self.spin_version = QSpinBox()
        self.spin_version.setRange(1, 40)
        self.spin_version.setValue(1)
        self.spin_version.setToolTip(
            "Versió del QR (1–40). Amb 'fit=True' s'ajusta automàticament.\n"
            "Deixa-ho a 1 per a la majoria de casos."
        )
        form.addRow("Versió:", self.spin_version)

        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 50)
        self.spin_size.setValue(10)
        self.spin_size.setSuffix(" px")
        self.spin_size.setToolTip("Mida en píxels de cada mòdul (quadret) del QR.")
        form.addRow("Mida de mòdul:", self.spin_size)

        self.spin_border = QSpinBox()
        self.spin_border.setRange(0, 20)
        self.spin_border.setValue(4)
        self.spin_border.setSuffix(" mòduls")
        self.spin_border.setToolTip(
            "Zona silenciosa al voltant del QR.\n"
            "L'estàndard recomana un mínim de 4."
        )
        form.addRow("Vora:", self.spin_border)

        self.combo_ec = QComboBox()
        self.combo_ec.addItems(list(_EC_DISPLAY_TO_KEY.keys()))
        self.combo_ec.setToolTip(
            "Nivell de correcció d'errors:\n"
            "  H = el QR és llegible fins i tot si un 30% és danyat.\n"
            "  L = menor redundància, QR més petit."
        )
        form.addRow("Correcció d'errors:", self.combo_ec)

        color_row = QHBoxLayout()
        self.btn_fill = ColorButton("#000000")
        self.btn_fill.setToolTip("Color dels mòduls del QR (foreground)")
        self.btn_back = ColorButton("#ffffff")
        self.btn_back.setToolTip("Color de fons del QR (background)")
        color_row.addWidget(self.btn_fill)
        color_row.addWidget(QLabel("Color mòduls"))
        color_row.addSpacing(20)
        color_row.addWidget(self.btn_back)
        color_row.addWidget(QLabel("Color fons"))
        color_row.addStretch()
        form.addRow("Colors:", color_row)

        box.set_content_layout(form)
        return box

    def _build_url_group(self) -> QGroupBox:
        """Crea el panell de la llista d'URLs amb selector de mode Manual / JSON."""
        group = QGroupBox("Llista d'URLs a codificar")
        layout = QVBoxLayout(group)

        # Selector de mode: l'usuari tria si introdueix les URLs a mà o des d'un JSON
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Origen:"))
        self._rb_manual = QRadioButton("Manual")
        self._rb_json   = QRadioButton("Des d'arxiu JSON")
        self._rb_manual.setChecked(True)
        self._url_mode_group = QButtonGroup(self)
        self._url_mode_group.addButton(self._rb_manual, 0)
        self._url_mode_group.addButton(self._rb_json,   1)
        self._url_mode_group.idToggled.connect(self._on_url_mode_changed)
        mode_row.addWidget(self._rb_manual)
        mode_row.addWidget(self._rb_json)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # Barra de botons visible en mode Manual
        self._manual_bar = QWidget()
        manual_row = QHBoxLayout(self._manual_bar)
        manual_row.setContentsMargins(0, 0, 0, 0)
        btn_add = QPushButton("＋  Afegir fila")
        btn_add.clicked.connect(lambda: self._add_url_row())
        btn_del = QPushButton("－  Eliminar fila")
        btn_del.clicked.connect(self._remove_url_row)
        btn_save = QPushButton("💾  Desar JSON...")
        btn_save.setToolTip("Desa la llista actual com a fitxer JSON reutilitzable")
        btn_save.clicked.connect(self._save_json)
        manual_row.addWidget(btn_add)
        manual_row.addWidget(btn_del)
        manual_row.addStretch()
        manual_row.addWidget(btn_save)
        layout.addWidget(self._manual_bar)

        # Barra de botons visible en mode JSON
        self._json_bar = QWidget()
        json_row = QHBoxLayout(self._json_bar)
        json_row.setContentsMargins(0, 0, 0, 0)
        btn_load = QPushButton("📂  Carregar JSON...")
        btn_load.setToolTip("Obre un fitxer JSON i omple la taula automàticament")
        btn_load.clicked.connect(self._load_json)
        json_row.addWidget(btn_load)
        json_row.addStretch()
        self._json_bar.setVisible(False)
        layout.addWidget(self._json_bar)

        # Taula editable amb dues columnes: nom del fitxer i URL
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Nom (serà el nom del fitxer .png)", "URL"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 200)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(130)

        layout.addWidget(self.table)
        return group

    def _build_output_group(self) -> CollapsibleBox:
        """Crea el panell plegable per triar el directori on es desaran els PNG."""
        box = CollapsibleBox("Directori de sortida dels fitxers .png")
        vbox = QVBoxLayout()
        vbox.setContentsMargins(8, 8, 8, 8)

        row = QHBoxLayout()
        self.edit_output = QLineEdit(".")
        self.edit_output.setPlaceholderText("Camí on es desaran els codis QR generats")
        btn_browse = QPushButton("Navegar...")
        btn_browse.setFixedWidth(100)
        btn_browse.clicked.connect(self._browse_output)
        row.addWidget(self.edit_output)
        row.addWidget(btn_browse)
        vbox.addLayout(row)
        vbox.addStretch()

        box.set_content_layout(vbox)
        return box

    def _build_log_group(self) -> QGroupBox:
        """Crea el panell del registre d'execució amb fons fosc i botó per netejar-lo."""
        group = QGroupBox("Registre d'execució")
        layout = QVBoxLayout(group)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        self.log_area.setMinimumHeight(91)
        self.log_area.setStyleSheet("background-color: #2c3e50;")
        layout.addWidget(self.log_area)

        btn_clear = QPushButton("Netejar registre")
        btn_clear.setFixedWidth(130)
        btn_clear.clicked.connect(self.log_area.clear)
        layout.addWidget(btn_clear, alignment=Qt.AlignRight)

        return group

    def _build_preview_group(self) -> QGroupBox:
        """Crea el panell de miniatures amb scroll horitzontal per als QRs generats."""
        group = QGroupBox("QRs generats  —  clic sobre la imatge per veure-la a mida real")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 6, 6, 6)

        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(100)
        scroll.setFrameShape(QFrame.NoFrame)

        # Contenidor horitzontal on s'afegiran les miniatures dinàmicament
        self._preview_container = QWidget()
        self._preview_layout = QHBoxLayout(self._preview_container)
        self._preview_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._preview_layout.setSpacing(10)
        self._preview_layout.setContentsMargins(2, 2, 2, 2)

        scroll.setWidget(self._preview_container)
        layout.addWidget(scroll)

        return group

    def _build_action_row(self) -> QHBoxLayout:
        """Crea la fila inferior amb el botó principal de generació de codis QR."""
        layout = QHBoxLayout()

        self.btn_generate = QPushButton("▶   Generar codis QR")
        self.btn_generate.setDefault(True)
        self.btn_generate.setFixedHeight(36)
        self.btn_generate.setStyleSheet(
            "QPushButton { background-color:#1a6fa8; color:white; font-weight:bold;"
            "              border-radius:4px; padding:6px 24px; }"
            "QPushButton:hover { background-color:#2980b9; }"
            "QPushButton:pressed { background-color:#145a86; }"
        )
        self.btn_generate.clicked.connect(self._on_generate)

        layout.addStretch()
        layout.addWidget(self.btn_generate)

        return layout

    # ------------------------------------------------------------------
    # Preview helpers — gestió del panell de miniatures
    # ------------------------------------------------------------------

    def _populate_preview(self, names_and_paths: list) -> None:
        """Buida les miniatures existents i en crea una per cada fitxer PNG generat."""
        while self._preview_layout.count():
            item = self._preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for name, path in names_and_paths:
            if path.exists():
                self._preview_layout.addWidget(self._make_thumbnail(name, path))

    def _make_thumbnail(self, name: str, path: Path) -> QToolButton:
        """Crea un botó-miniatura clicable amb la imatge QR escalada i el nom a sota."""
        btn = QToolButton()
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        px = QPixmap(str(path))
        if px.isNull():
            # Si no es pot carregar la imatge, mostra un quadrat gris de substitució
            px = QPixmap(QSize(70, 70))
            px.fill(QColor("#cccccc"))
        btn.setIcon(QIcon(px.scaled(QSize(70, 70), Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        btn.setIconSize(QSize(70, 70))
        label = name if len(name) <= 18 else name[:16] + "…"
        btn.setText(label)
        btn.setFixedWidth(90)
        btn.setToolTip(f"{name}\n{path}")
        btn.clicked.connect(lambda _checked=False, p=path, n=name: self._show_full_qr(p, n))
        return btn

    def _show_full_qr(self, path: Path, name: str) -> None:
        """Obre un diàleg emergent que mostra el codi QR a mida completa (450×450 px)."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"QR — {name}")
        dlg.setModal(True)
        v = QVBoxLayout(dlg)

        lbl_img = QLabel()
        px = QPixmap(str(path))
        lbl_img.setPixmap(px.scaled(QSize(450, 450), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lbl_img.setAlignment(Qt.AlignCenter)

        lbl_info = QLabel(f"<b>{name}</b><br><small>{path.resolve()}</small>")
        lbl_info.setAlignment(Qt.AlignCenter)
        lbl_info.setWordWrap(True)

        v.addWidget(lbl_img)
        v.addWidget(lbl_info)
        dlg.adjustSize()
        dlg.exec()

    # ------------------------------------------------------------------
    # Menu — barra de menú i diàleg "Quant a..."
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        """Crea la barra de menú amb l'entrada 'Ajuda → Quant a...' (drecera: F1)."""
        help_menu = self.menuBar().addMenu("Ajuda")

        about_action = QAction("Quant a QR Generator...", self)
        about_action.setShortcut("F1")
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        """Mostra el diàleg d'informació: versió, descripció, autor i enllaços."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Quant a QR Code Generator")
        dlg.setFixedWidth(400)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 22, 28, 22)

        lbl_title = QLabel("<h2 style='margin:0'>QR Code Generator</h2>")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_version = QLabel(f"<p style='color:#777; margin:4px 0 0 0'>Versió {__version__}</p>")
        lbl_version.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_version)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep1)

        lbl_desc = QLabel(
            "Genera codis QR en format PNG a partir d'URLs,<br>"
            "directament i sense dependre de servidors externs.<br>"
            "Els codis generats no caduquen i no requereixen connexió."
        )
        lbl_desc.setAlignment(Qt.AlignCenter)
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        lbl_author = QLabel(
            f"<b>{_AUTHOR}</b><br><br>"
            f"🌐 &nbsp;<a href='{_WEB}'>{_WEB.replace('https://', '')}</a><br>"
            f"📦 &nbsp;<a href='{_GITHUB}'>{_GITHUB.replace('https://', '')}</a><br>"
            f"✉ &nbsp;<a href='mailto:{_EMAIL}'>{_EMAIL}</a>"
        )
        lbl_author.setAlignment(Qt.AlignCenter)
        lbl_author.setOpenExternalLinks(True)
        lbl_author.setTextInteractionFlags(Qt.TextBrowserInteraction)
        layout.addWidget(lbl_author)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep3)

        lbl_license = QLabel("Llicència: MIT")
        lbl_license.setAlignment(Qt.AlignCenter)
        lbl_license.setStyleSheet("color:#999; font-size:11px;")
        layout.addWidget(lbl_license)

        btn_close = QPushButton("Tancar")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignCenter)

        dlg.exec()

    # ------------------------------------------------------------------
    # Logging setup — configuració del sistema de registre
    # ------------------------------------------------------------------

    def _init_logging(self) -> None:
        """Configura dos handlers de log: fitxer amb timestamp i panell visual de la GUI."""
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"qr_{timestamp}.log"

        fmt_file = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        fmt_gui = logging.Formatter(
            "%(asctime)s [%(levelname)-5s] %(message)s", datefmt="%H:%M:%S"
        )

        file_h = logging.FileHandler(log_path, encoding="utf-8")
        file_h.setFormatter(fmt_file)

        gui_h = _QTextEditHandler(self.log_area)
        gui_h.setFormatter(fmt_gui)

        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(file_h)
        root.addHandler(gui_h)

        logging.getLogger(__name__).info("Aplicació iniciada · Log: %s", log_path)

    # ------------------------------------------------------------------
    # URL table helpers — operacions sobre la taula d'URLs
    # ------------------------------------------------------------------

    def _add_url_row(self, name: str = "", url: str = "") -> None:
        """Afegeix una nova fila a la taula d'URLs i hi posa el focus."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(url))
        self.table.scrollToBottom()
        self.table.setCurrentCell(row, 0)

    def _remove_url_row(self) -> None:
        """Elimina les files seleccionades; si no n'hi ha, elimina l'última."""
        selected = sorted(
            {idx.row() for idx in self.table.selectedIndexes()}, reverse=True
        )
        if not selected and self.table.rowCount() > 0:
            selected = [self.table.rowCount() - 1]
        for row in selected:
            self.table.removeRow(row)

    def _on_url_mode_changed(self, button_id: int, checked: bool) -> None:
        """Canvia la barra de botons i l'edició de la taula segons el mode seleccionat."""
        if not checked:
            return
        is_manual = (button_id == 0)
        self._manual_bar.setVisible(is_manual)
        self._json_bar.setVisible(not is_manual)
        # En mode JSON la taula és de només lectura per evitar edicions accidentals
        triggers = (
            QAbstractItemView.AllEditTriggers if is_manual
            else QAbstractItemView.NoEditTriggers
        )
        self.table.setEditTriggers(triggers)

    # ------------------------------------------------------------------
    # Browse — navegació del sistema de fitxers
    # ------------------------------------------------------------------

    def _browse_output(self) -> None:
        """Obre el diàleg del sistema per triar el directori de sortida dels PNG."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecciona el directori de sortida",
            self.edit_output.text() or ".",
        )
        if folder:
            self.edit_output.setText(folder)

    # ------------------------------------------------------------------
    # Config build / load — construcció i càrrega de la configuració
    # ------------------------------------------------------------------

    def _build_config(self) -> dict:
        """Llegeix tots els camps del formulari i retorna el diccionari de configuració."""
        urls = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            url_item  = self.table.item(row, 1)
            name = (name_item.text().strip() if name_item else "")
            url  = (url_item.text().strip()  if url_item  else "")
            if name or url:
                urls.append([name, url])

        return {
            "version":          self.spin_version.value(),
            "size":             self.spin_size.value(),
            "border":           self.spin_border.value(),
            "fill_col":         self.btn_fill.color_hex(),
            "back_col":         self.btn_back.color_hex(),
            "error_correction": _EC_DISPLAY_TO_KEY[self.combo_ec.currentText()],
            "urls":             urls,
        }

    def _populate_form(self, config: dict) -> None:
        """Omple tots els camps del formulari a partir d'un diccionari de configuració."""
        self.spin_version.setValue(int(config.get("version", 1)))
        self.spin_size.setValue(int(config.get("size", 10)))
        self.spin_border.setValue(int(config.get("border", 4)))
        self.btn_fill.set_color(config.get("fill_col", "#000000"))
        self.btn_back.set_color(config.get("back_col", "#ffffff"))

        ec_key = str(config.get("error_correction", "H")).upper()
        display = _EC_KEY_TO_DISPLAY.get(ec_key, list(_EC_DISPLAY_TO_KEY)[0])
        idx = self.combo_ec.findText(display)
        if idx >= 0:
            self.combo_ec.setCurrentIndex(idx)

        self.table.setRowCount(0)
        for entry in config.get("urls", []):
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                self._add_url_row(str(entry[0]), str(entry[1]))

    # ------------------------------------------------------------------
    # Slots — accions desencadenades pels botons
    # ------------------------------------------------------------------

    def _load_json(self) -> None:
        """Obre un fitxer JSON i carrega tota la seva configuració al formulari."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Carregar configuració JSON", "", "Fitxers JSON (*.json);;Tots (*)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                config = json.load(f)
            self._populate_form(config)
            logging.getLogger(__name__).info("Config carregada des de: %s", path)
        except (json.JSONDecodeError, OSError) as exc:
            QMessageBox.critical(self, "Error en carregar", str(exc))

    def _save_json(self) -> None:
        """Desa la configuració actual del formulari com a fitxer JSON."""
        config = self._build_config()
        path, _ = QFileDialog.getSaveFileName(
            self, "Desar configuració JSON", "QR_CONFIG.json", "Fitxers JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logging.getLogger(__name__).info("Config desada a: %s", path)
        except OSError as exc:
            QMessageBox.critical(self, "Error en desar", str(exc))

    def _on_generate(self) -> None:
        """Valida la configuració, crida el generador de QRs i actualitza la previsualització."""
        config = self._build_config()

        try:
            _validate_config(config)
        except ValueError as exc:
            QMessageBox.warning(self, "Error de configuració", str(exc))
            return

        output_dir = Path(self.edit_output.text().strip() or ".")
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("Generant...")

        try:
            errors = generate(config, output_dir)
        finally:
            self.btn_generate.setEnabled(True)
            self.btn_generate.setText("▶   Generar codis QR")

        # Calcula les rutes esperades dels PNG per mostrar les miniatures
        names_and_paths = [
            (name, output_dir / f"qrcode_{_safe_filename(name)}.png")
            for name, _url in config["urls"]
        ]
        self._populate_preview(names_and_paths)

        total = len(config["urls"])
        ok = total - errors

        if errors == 0:
            QMessageBox.information(
                self,
                "Completat",
                f"✔  {ok} de {total} codis QR generats correctament.\n\nDesti: {output_dir.resolve()}",
            )
        else:
            QMessageBox.warning(
                self,
                "Completat amb errors",
                f"{ok} de {total} codis QR generats.\n"
                f"{errors} error(s) — consulta el registre per a més detalls.",
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Inicialitza l'aplicació Qt, aplica l'estil Fusion i obre la finestra principal."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
