#!/usr/bin/env python
import atexit
import logging
import os
import sys
import tempfile
from copy import deepcopy
from decimal import Decimal
from enum import Enum
from pathlib import Path

import platformdirs
import pydicom.config
import pydicom.datadict
import pydicom.dataset
from dcm_mini_viewer.config.preferences_manager import (
    PreferencesManager as MiniViewerPrefs,
)
from dcm_mini_viewer.main import MainWindow as DcmMiniViewer
from pydicom import DataElement, Dataset, Sequence, dcmread, dcmwrite
from pydicom.datadict import dictionary_VR
from pydicom.dataelem import RawDataElement
from pydicom.multival import MultiValue
from pydicom.tag import BaseTag
from pydicom.valuerep import VR
from pynetdicom.presentation import build_context

# pylint: disable=no-name-in-module
from PySide6.QtCore import QEvent, Qt, Slot
from PySide6.QtGui import QAction, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QApplication,
    QFileDialog,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QWhatsThis,
)

from dcmqtreepy.add_private_element_dialog import AddPrivateElementDialog
from dcmqtreepy.add_public_element_dialog import AddPublicElementDialog
from dcmqtreepy.import_hex_legible_private_element_lists import (
    pydicom_private_dicts_from_json,
)
from dcmqtreepy.mainwindow import Ui_MainWindow
from dcmqtreepy.new_privates import new_private_dictionaries
from dcmqtreepy.qt_assistant_launcher import HelpAssistant

logger = logging.getLogger(__name__)

# VRs whose value is a byte payload. Their value cells are not editable, and a change to one is refused (#64).
BINARY_VRS = frozenset({VR.OB, VR.OW, VR.OB_OW, VR.OD, VR.OF, VR.OL, VR.OV, VR.UN})
INT_VRS = frozenset({"SS", "US", "SL", "UL", "SV", "UV"})
FLOAT_VRS = frozenset({"FL", "FD", "DS"})
# Always VM 1, and a backslash is legal inside the value, so their cell text is never split (#64).
SINGLE_VALUED_TEXT_VRS = frozenset({"LT", "ST", "UT", "UR"})

# VRs whose Explicit VR encoding has a 16-bit Value Length field (PS3.5 7.1.2). A value of one of these longer than
# 0xFFFE cannot be written in Explicit VR except as UN (PS3.5 6.2.2, CP-1066) (#79).
SHORT_LENGTH_VRS = frozenset(
    {
        "AE",
        "AS",
        "AT",
        "CS",
        "DA",
        "DS",
        "DT",
        "FL",
        "FD",
        "IS",
        "LO",
        "LT",
        "PN",
        "SH",
        "SL",
        "SS",
        "ST",
        "TM",
        "UI",
        "UL",
        "US",
    }
)
MAX_SHORT_VALUE_LENGTH = 0xFFFE
_BINARY_NUMBER_SIZES = {"AT": 4, "FL": 4, "FD": 8, "SL": 4, "SS": 2, "UL": 4, "US": 2}


class OversizedChoice(Enum):
    """How to save an Implicit VR source holding a value too long for Explicit VR (#79)."""

    KEEP_IMPLICIT = "keep_implicit"
    EXPLICIT_WITH_UN = "explicit_with_un"


def _element_vr(tag: BaseTag, elem) -> str | None:
    """The element's VR, from the dictionary when an Implicit VR raw element carries none."""
    if elem.VR:
        return str(elem.VR)
    if tag.is_private:
        return None
    try:
        return dictionary_VR(tag)
    except KeyError:
        return None


def encoded_value_length(elem: DataElement) -> int:
    """The length of elem's value as encoded, without encoding it (#79).

    Only the VRs in SHORT_LENGTH_VRS are measured; any other VR returns 0. Text values are measured by their
    backslash-joined form, padded to even length; binary numbers by count times size.
    """
    vr = str(elem.VR)
    if vr not in SHORT_LENGTH_VRS or elem.value is None:
        return 0
    values = list(elem.value) if isinstance(elem.value, (list, tuple, MultiValue)) else [elem.value]
    if vr in _BINARY_NUMBER_SIZES:
        return len(values) * _BINARY_NUMBER_SIZES[vr]
    text = "\\".join(getattr(v, "original_string", None) or str(v) for v in values)
    length = len(text.encode("utf-8", errors="replace"))
    return length + (length % 2)


def find_oversized_elements(ds: Dataset) -> list[tuple[Dataset, BaseTag]]:
    """Every element, at any depth, whose VR has a 16-bit length field and whose value is longer than 0xFFFE (#79).

    Raw elements are measured by their recorded length, so their values are not converted; that is what makes this
    cheap enough to run on every load (108 ms against 11.6 s for converting, on a 58.5 MB RT Structure Set).
    Sequences are parsed to reach their items. Returns (dataset holding the element, tag) pairs.
    """
    found: list[tuple[Dataset, BaseTag]] = []
    for tag in list(ds.keys()):
        elem = ds.get_item(tag)
        vr = _element_vr(tag, elem)
        if vr == "SQ" or (vr is None and isinstance(elem, RawDataElement) and elem.length == 0xFFFFFFFF):
            for item in ds[tag].value:
                found.extend(find_oversized_elements(item))
        elif vr in SHORT_LENGTH_VRS:
            length = elem.length if isinstance(elem, RawDataElement) else encoded_value_length(elem)
            if length > MAX_SHORT_VALUE_LENGTH:
                found.append((ds, BaseTag(tag)))
    return found


def choose_transfer_syntax(
    source_ts: str | None, has_oversized: bool, choice: OversizedChoice = OversizedChoice.KEEP_IMPLICIT
) -> tuple[str, bool]:
    """The (TransferSyntaxUID, is_implicit_VR) to save with (#57, #79).

    Implicit VR LE (or no syntax recorded) becomes Explicit VR LE, so the file carries its VRs, unless a value is too
    long for Explicit VR: then the choice decides. Every other source syntax is kept: converting big endian corrupts
    pixel bytes, and Explicit VR LE and encapsulated syntaxes already carry VRs.
    """
    if not source_ts or source_ts == pydicom.uid.ImplicitVRLittleEndian:
        if has_oversized and choice is OversizedChoice.KEEP_IMPLICIT:
            return pydicom.uid.ImplicitVRLittleEndian, True
        return pydicom.uid.ExplicitVRLittleEndian, False
    return source_ts, False


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def _get_umask() -> int:
    """Get the current umask (only safe way is to set it and restore)."""
    old = os.umask(0)
    os.umask(old)
    return old


class DCMQtreePy(QMainWindow):
    def __init__(self, parent=None):
        # Force non-native menubar, otherwise getting help while on the menu doesn't work
        QApplication.instance().setAttribute(Qt.AA_DontUseNativeMenuBar, True)

        super().__init__(parent)
        self.ui = Ui_MainWindow()

        self.ui.setupUi(self)
        self.logger = logging.getLogger(__name__)
        self.dcm_tree_widget = self.ui.treeWidget
        self.dcm_tree_widget.editTriggers = self.dcm_tree_widget.EditTrigger.NoEditTriggers
        header = self.dcm_tree_widget.header()
        header.setMinimumSectionSize(40)  # characters or pixels?
        header.setDefaultSectionSize(200)  # pixels
        # header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # header.setStretchLastSection(False)
        # header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.dcm_tree_widget.itemDoubleClicked.connect(self.on_tree_widget_item_double_clicked)
        self.dcm_tree_widget.itemChanged.connect(self.on_tree_item_changed)
        self.ui.listWidget.itemSelectionChanged.connect(self.on_item_selection_changed)
        #     self.tree_del_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.dcm_tree_widget)
        #     self.tree_del_shortcut.activated.connect(self.handle_tree_delete_pressed)
        self.file_list_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.ui.listWidget)
        self.file_list_shortcut.activated.connect(self.handle_file_list_delete_pressed)
        #     self.del_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self)
        #     self.del_shortcut.activated.connect(lambda : QMessageBox.information(self,
        # 'Message', 'Del initiated'))
        self.ui.actionOpen.triggered.connect(self.on_file_open)
        self.ui.actionSave.triggered.connect(self.on_file_save)
        self.ui.actionSave_As.triggered.connect(self.on_file_save_as)
        self.ui.actionAdd_Element.triggered.connect(self.on_add_element)
        self.ui.actionAdd_Private_Element.triggered.connect(self.on_add_private_element)
        self.ui.actionDelete.triggered.connect(self.handle_file_list_delete_pressed)
        self.ui.actionDelete_Element.triggered.connect(self.handle_tree_delete_pressed)
        self.ui.actionView_Image.triggered.connect(self.on_view_image)
        self.previous_path = Path().home()
        self.previous_save_path = Path().home()
        self.current_list_item = None
        self.reverting_list_item = False
        self.current_dataset = Dataset()
        self._pruned_creators: list[tuple] = []  # (creator_tag, dataset_ref) for exact prune
        self._pending_errors: dict[int, Exception] = {}  # keyed by id(row) — same tag in root+item are distinct
        # Values too long for Explicit VR: (dataset holding the element, tag), recorded at load from raw lengths (#79)
        self._oversized: list[tuple[Dataset, BaseTag]] = []
        self.has_edits = False
        pydicom.config.Settings.writing_validation_mode = pydicom.config.RAISE
        logging.info("Loading Known Private Dictionaries")
        for creator, private_dict in new_private_dictionaries.items():
            try:
                pydicom.datadict.add_private_dict_entries(creator, private_dict)
                logging.warning(f"Private dictionary for {creator} has been loaded")
            except ValueError:
                logging.error(f"Unable to load private dictionary for {creator}")

        json_privates_file = "local_privates.json"
        if Path(json_privates_file).exists():
            logging.info(f"Loading Private Dictionaries from {json_privates_file}")

            try:
                private_dictionaries_from_json = pydicom_private_dicts_from_json(json_privates_file)
                for creator, private_dict in private_dictionaries_from_json.items():
                    try:
                        pydicom.datadict.add_private_dict_entries(creator, private_dict)
                        logging.warning(f"Private dictionary for {creator} has been loaded")
                    except ValueError:
                        logging.error(f"Unable to load private dictionary for {creator}")
            except Exception as json_privates_exc:
                logging.error(json_privates_exc)

        # In __init__ after setting up the UI
        self.installEventFilter(self)
        QApplication.instance().installEventFilter(self)

        self.help_assistant = HelpAssistant(self)
        self.help_assistant.setup_assistant(resource_path("help/dcmqtreepy-qhcp.qhc"))
        # Register cleanup with atexit
        atexit.register(self.help_assistant.cleanup)

        # Connect F1 key to context-sensitive help
        self.help_shortcut_f1 = QShortcut(QKeySequence("F1"), self)
        self.help_shortcut_f1.activated.connect(self.show_context_help)
        self.help_shortcut_f1.setContext(Qt.ApplicationShortcut)  # Make it work application-wide

        # Set help_id properties for various widgets
        self.setProperty("help_id", "dicom")
        self.ui.actionOpen.setProperty("help_id", "open_file")
        self.ui.actionSave.setProperty("help_id", "save_file")
        self.ui.actionSave_As.setProperty("help_id", "save_as_file")
        self.ui.actionAdd_Element.setProperty("help_id", "add_element")
        self.ui.actionAdd_Private_Element.setProperty("help_id", "add_private_element")
        self.ui.actionDelete.setProperty("help_id", "delete_file")
        self.ui.actionDelete_Element.setProperty("help_id", "delete_element")

        self.dcm_tree_widget.setProperty("help_id", "dicom_tree")
        self.ui.listWidget.setProperty("help_id", "file_list")

        # pydicom.datadict.add_private_dict_entries("IMPAC", impac_privates.impac_private_dict)
        # Track current menu context
        self.current_menu_action = None

        # Connect all actions to track when they're hovered
        # Correctly access the menu bar and all its actions
        menu_bar = self.menuBar()
        for menu in menu_bar.findChildren(QMenu):
            for action in menu.actions():
                action.hovered.connect(lambda act=action: self.track_menu_action(act))
        # # Connect all menu actions to track when they're hovered
        # for action in self.ui.actionOpen.parentWidget().actions():
        #     action.hovered.connect(lambda act=action: self.track_menu_action(act))
        # Set up context-sensitive help for menu actions
        self.setup_action_help()
        self.image_viewer_prefs = MiniViewerPrefs()
        self.image_viewer_prefs.initialize()
        self.image_viewer = DcmMiniViewer(self.image_viewer_prefs)

    def setup_action_help(self):
        """Set up context-sensitive help for all menu actions"""
        # File menu actions
        self.ui.actionOpen.setWhatsThis("Opens a DICOM file")
        self.ui.actionSave.setWhatsThis("Saves the current DICOM file")
        self.ui.actionSave_As.setWhatsThis("Saves the current DICOM file with a new name")
        self.ui.actionAdd_Element.setWhatsThis("Adds a new public DICOM element")
        self.ui.actionAdd_Private_Element.setWhatsThis("Adds a new private DICOM element")
        self.ui.actionDelete.setWhatsThis("Deletes the selected item")
        self.ui.actionDelete_Element.setWhatsThis("Deletes the selected DICOM element")

        # Also map these actions to help context IDs for F1 help
        self.ui.actionOpen.setProperty("help_id", "open_file")
        self.ui.actionSave.setProperty("help_id", "save_file")
        self.ui.actionSave_As.setProperty("help_id", "save_as_file")
        self.ui.actionAdd_Element.setProperty("help_id", "add_element")
        self.ui.actionAdd_Private_Element.setProperty("help_id", "add_private_element")
        self.ui.actionDelete.setProperty("help_id", "delete_file")
        self.ui.actionDelete_Element.setProperty("help_id", "delete_element")

        # Create Help menu
        self.setup_help_menu()

    def setup_help_menu(self):
        """Create a Help menu with direct topic links"""
        help_menu = self.menuBar().addMenu("&Help")

        # Add standard "What's This" action
        whats_this_action = QWhatsThis.createAction(self)
        whats_this_action.setText("Context Help Mode")
        whats_this_action.setShortcut("Shift+F1")
        help_menu.addAction(whats_this_action)

        help_menu.addSeparator()

        # Add direct topic links
        help_menu.addAction("dcmQTreePy Overview").triggered.connect(lambda: self.help_assistant.show_help_topic("dicom"))

        help_menu.addAction("File Operations").triggered.connect(
            lambda: self.help_assistant.show_help_topic("file_operations")
        )

        help_menu.addAction("Editing DICOM Elements").triggered.connect(
            lambda: self.help_assistant.show_help_topic("dicom_elements")
        )

        help_menu.addAction("Private Elements").triggered.connect(
            lambda: self.help_assistant.show_help_topic("private_elements")
        )

        help_menu.addAction("Keyboard Shortcuts").triggered.connect(
            lambda: self.help_assistant.show_help_topic("keyboard_shortcuts")
        )

    def track_menu_action(self, action):
        """Keep track of which menu action is currently highlighted"""
        self.current_menu_action = action
        self.logger.debug(f"Current menu action: {action.text()}")

        if help_id := action.property("help_id"):
            self.logger.debug(f"Action has help_id: {help_id}")

    @staticmethod
    def _value_row_flags(elem: DataElement) -> Qt.ItemFlag:
        """Flags for an element row: editable unless its value is a byte payload (#64)."""
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if elem.VR not in BINARY_VRS:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    @staticmethod
    def _value_cell_text(elem: DataElement) -> str:
        """The text shown in an element row's value cell. OB/OW/OD/OF payloads are not shown."""
        if elem.VR in (VR.OB, VR.OW, VR.OB_OW, VR.OD, VR.OF):
            return ""
        if elem.value is None:
            return ""
        if isinstance(elem.value, (MultiValue, list)):
            # The DICOM form, so the cell parses back into the same values (#64)
            return "\\".join(str(v) for v in elem.value)
        return str(elem.value)

    @staticmethod
    def _parse_value_cell_text(text: str, vr: str):
        """A value cell's text as the value for vr: components separated by backslash, as DICOM encodes them (#64).

        LT, ST, UT and UR are single-valued and taken as typed. An empty cell clears the value. Numeric components
        are converted by VR, and one that does not convert raises ValueError.
        """
        if vr in SINGLE_VALUED_TEXT_VRS:
            return text
        convert = int if vr in INT_VRS else float if vr in FLOAT_VRS else None
        if text == "":
            return "" if convert is None else None
        parts = text.split("\\")
        values = parts if convert is None else [convert(part) for part in parts]
        return values[0] if len(values) == 1 else values

    def _populate_tree_widget_item_from_element(self, parent: QTreeWidgetItem | QTreeWidget, elem: DataElement):
        if elem.VR != VR.SQ:
            tree_child_item = QTreeWidgetItem(parent)
            tree_child_item.setFlags(self._value_row_flags(elem))
            tree_child_item.setText(0, str(elem.tag))
            tree_child_item.setText(1, elem.name)
            tree_child_item.setText(2, self._value_cell_text(elem))
            tree_child_item.setText(3, str(elem.VR))
            tree_child_item.setText(4, elem.keyword)
        else:
            tree_child_item = QTreeWidgetItem(parent)
            tree_child_item.setText(0, str(elem.tag))
            tree_child_item.setText(1, elem.name)
            tree_child_item.setText(3, str(elem.VR))
            tree_child_item.setText(4, elem.keyword)
            seq_item_count = 0
            for seq_item in elem:
                seq_item_count += 1
                seq_child_item = QTreeWidgetItem(tree_child_item)
                seq_child_item.setText(0, str(elem.tag))
                seq_child_item.setText(1, elem.name)
                seq_child_item.setText(2, str(seq_item_count))
                seq_child_item.setText(3, str(elem.VR))
                seq_child_item.setText(4, elem.keyword)
                self._populate_tree_widget_item_from_dataset(seq_child_item, seq_item)

    def _populate_tree_widget_item_from_dataset(self, parent: QTreeWidgetItem | QTreeWidget, ds: Dataset):
        for elem in ds:
            if elem.VR != VR.SQ:
                tree_child_item = QTreeWidgetItem(parent)
                tree_child_item.setFlags(self._value_row_flags(elem))
                tree_child_item.setText(0, str(elem.tag))
                tree_child_item.setText(1, elem.name)
                tree_child_item.setText(2, self._value_cell_text(elem))
                tree_child_item.setText(3, str(elem.VR))
                tree_child_item.setText(4, elem.keyword)
            else:
                tree_child_item = QTreeWidgetItem(parent)
                tree_child_item.setText(0, str(elem.tag))
                tree_child_item.setText(1, elem.name)
                tree_child_item.setText(3, str(elem.VR))
                tree_child_item.setText(4, elem.keyword)
                for seq_item_count, seq_item in enumerate(elem, start=1):
                    seq_child_item = QTreeWidgetItem(tree_child_item)
                    seq_child_item.setText(0, str(elem.tag))
                    seq_child_item.setText(1, elem.name)
                    seq_child_item.setText(2, str(seq_item_count))
                    seq_child_item.setText(3, str(elem.VR))
                    seq_child_item.setText(4, elem.keyword)
                    self._populate_tree_widget_item_from_dataset(seq_child_item, seq_item)

    def _populate_dataset_from_tree_widget_item(
        self,
        parent_ds: Dataset | Sequence | list,
        tree_widget_item: QTreeWidgetItem,
        private_block: pydicom.dataset.PrivateBlock = None,
    ) -> pydicom.dataset.PrivateBlock:
        tag_as_string = tree_widget_item.text(0)
        # name_as_string = tree_widget_item.text(1)
        value_as_string = tree_widget_item.text(2)
        vr_as_string = tree_widget_item.text(3)
        tag = self._convert_tag_as_string_to_tuple(tag_as_string)
        is_private = False

        # if tag[0] == 0x300a and tag[1] == 0x0782:
        #     raise ValueError("There is no 0x300a0782 element")
        if tag[0] % 2 == 1:
            # print(f"Private Element: {tag}")
            is_private = True
            group = tag[0]
            private_block_byte = tag[1] % 256  # lower 8 bits...
            if private_block_byte == 0x10:
                private_creator = value_as_string
                private_block = parent_ds.private_block(group, private_creator, create=True)
                return private_block
                # parent_ds.private_creators()
        else:
            private_block = None
        tag = tree_widget_item.text(4)  # keyword

        if vr_as_string == "SQ":
            if value_as_string is None or value_as_string == "":
                #    seq_elem = DataElement(tag=tag,VR=vr_as_string,value=Sequence())
                #    parent_ds.add(seq_elem)
                parent_ds.add(DataElement(tag=tag, VR=vr_as_string, value=None))
                # parent_ds[tag]= Sequence()
                seq_elem = parent_ds[tag]
                for child_index in range(tree_widget_item.childCount()):
                    child = tree_widget_item.child(child_index)
                    private_block = self._populate_dataset_from_tree_widget_item(
                        parent_ds=seq_elem, tree_widget_item=child, private_block=private_block
                    )
            else:
                # item_number = int(value_as_string)
                child_ds = Dataset()
                my_list = parent_ds.value
                my_list.append(child_ds)
                for child_index in range(tree_widget_item.childCount()):
                    child = tree_widget_item.child(child_index)
                    private_block = self._populate_dataset_from_tree_widget_item(
                        parent_ds=child_ds, tree_widget_item=child, private_block=private_block
                    )

        elif len(vr_as_string) > 0:  # if there isn't a VR, there's no point in encoding
            if len(value_as_string) > 0 and value_as_string[0] == "[":
                my_list_of_values = value_as_string.split("[")[1].split("]")[0].split(",")
                cast_list_of_values = my_list_of_values
                if vr_as_string in [VR.IS, VR.SS, VR.US]:
                    cast_list_of_values = [int(x) for x in my_list_of_values]
                elif vr_as_string in [VR.DS, VR.FL, VR.FD]:
                    cast_list_of_values = [float(x) for x in my_list_of_values]
                else:
                    cast_list_of_values = [x.strip('"').strip(" ").strip("'") for x in my_list_of_values]

                if is_private:
                    if private_block is not None:
                        private_block.add_new(private_block_byte, vr_as_string, cast_list_of_values)
                    else:
                        logging.warning(
                            f"Private element {group:04x},{private_block_byte:02x} found with no private block parent"
                        )
                        known_private_creators = parent_ds.private_creators(group)
                        if len(known_private_creators) == 1:
                            known_private_creator = known_private_creators[0]
                            private_block = parent_ds.private_block(group, private_creator=known_private_creator, create=True)
                            private_block.add_new(private_block_byte, vr_as_string, cast_list_of_values)
                            logging.warning("Found a private creator to attach private element to")
                        else:
                            logging.error(
                                f"Unable to find private creator for Private \
                                    element {group:04x},{private_block_byte:02x} element can not be copied/saved"
                            )

                else:
                    elem = DataElement(tag=tag, VR=vr_as_string, value=cast_list_of_values)
            else:
                try:
                    cast_value = value_as_string
                    if len(value_as_string) > 0:
                        if vr_as_string in [VR.SS, VR.US]:
                            cast_value = int(value_as_string)
                        elif vr_as_string in [VR.FL, VR.FD]:
                            cast_value = float(value_as_string)
                    elif vr_as_string in [VR.SS, VR.US, VR.FL, VR.FD]:
                        cast_value = None
                    if is_private:
                        if private_block is not None:
                            private_block.add_new(private_block_byte, vr_as_string, cast_value)
                        else:
                            logging.warning(
                                f"Private element {group:04x},{private_block_byte:02x} found with no private block parent"
                            )
                            known_private_creators = parent_ds.private_creators(group)
                            if len(known_private_creators) == 1:
                                known_private_creator = known_private_creators[0]
                                private_block = parent_ds.private_block(
                                    group, private_creator=known_private_creator, create=True
                                )
                                private_block.add_new(private_block_byte, vr_as_string, cast_value)
                                logging.warning("Found a private creator to attach private element to")
                            else:
                                logging.error(
                                    f"Unable to find private creator for Private \
                                        element {group:04x},{private_block_byte:02x} element can not be copied/saved"
                                )

                    else:
                        elem = DataElement(tag=tag, VR=vr_as_string, value=cast_value)
                except ValueError as encoding_error:
                    logging.error(f"{tag} {tag_as_string} {encoding_error}")
            if not is_private:
                parent_ds.add(elem)
        return private_block

    def _convert_text_lines_to_vr_values(self, text_lines: str, vr_as_string: str) -> list:
        text_list = text_lines.splitlines()
        cast_values = []
        for value_as_string in text_list:
            try:
                cast_value = value_as_string
                if len(value_as_string) > 0:
                    if vr_as_string in [VR.IS, VR.SS, VR.US]:
                        cast_value = int(value_as_string)
                    elif vr_as_string in [VR.FL, VR.FD]:
                        cast_value = float(value_as_string)
                    elif vr_as_string in [VR.DS]:
                        cast_value = Decimal(value_as_string)
                elif vr_as_string in [VR.SS, VR.US, VR.FL, VR.FD]:
                    cast_value = None
            except Exception:
                logging.error(f"Failed in casting {value_as_string} to VR of {vr_as_string}")
                return []
            cast_values.append(cast_value)
        return cast_values

    def _convert_tag_as_string_to_tuple(self, tag_as_string: str) -> tuple[int, int]:
        first_split = tag_as_string.split("(")[1]
        group = first_split.split(",")[0]
        elem_hex_as_string = first_split.split(",")[1].split(")")[0]
        return (int(group, 16), int(elem_hex_as_string, 16))

    def _isEditable(self, column: int) -> bool:
        return column == 2

    def on_item_selection_changed(self):
        if self.reverting_list_item:
            self.reverting_list_item = False
            return
        prev_item = self.current_list_item
        if self.has_edits:
            button = self.non_native_warning_message(
                title="Current Tree Has Edits",
                text="Continuing will lose current edits",
                buttons=QMessageBox.Ok | QMessageBox.Cancel,
            )
            if button == QMessageBox.Cancel:
                if prev_item is not None:
                    self.reverting_list_item = True
                    self.ui.listWidget.setCurrentItem(prev_item)
                return
        current_item = self.ui.listWidget.currentItem()
        self.current_list_item = current_item
        self.populate_tree_widget_from_file(current_item.text())

    def on_tree_widget_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        if self._isEditable(column):
            self.dcm_tree_widget.editItem(item, column)
        else:
            print(f"Column {column} is not editable")

    def on_view_image(self):
        if not self.current_list_item:
            return
        try:
            file_path = self.current_list_item.text()
            self.image_viewer.dicom_handler.load_file(file_path)
            # Display the image
            self.image_viewer.display_dicom_image()

            # Display metadata
            self.image_viewer.display_metadata()

            # Update status bar
            self.image_viewer.statusBar().showMessage(f"Loaded {file_path}")
            self.image_viewer.show()
        except Exception as e:
            logging.error(f"Failed to load or display DICOM image {file_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Could not load DICOM image:\n{e}")

    def on_file_open(self):
        previous_path = self.previous_path
        file_name, ok = QFileDialog.getOpenFileName(self, "Open DICOM File", str(previous_path), "DICOM Files (*.dcm)")
        if file_name:
            file_list_item = QListWidgetItem(str(file_name))
            self.ui.listWidget.addItem(file_list_item)
            self.populate_tree_widget_from_file(file_name)
            self.current_list_item = file_list_item

    def populate_tree_widget_from_file(self, file_name: str | Path):
        if file_name:
            path = Path(file_name)
            self.previous_path = path.parent
            ds = dcmread(path, force=True)
            # Before the tree build converts every value, while raw lengths are still free to read (#79)
            self._oversized = find_oversized_elements(ds)
            # ds.remove_private_tags() # temporarily, until save as is working.
            self.current_dataset = ds
            self._pending_errors.clear()  # clear per-file (cora 13021 #8)
            self.dcm_tree_widget.blockSignals(True)
            # Unblock even if building raises: blocked signals would keep later edits out of the dataset (#68)
            try:
                self.dcm_tree_widget.clear()
                tree_child_item = QTreeWidgetItem(self.dcm_tree_widget)
                context = build_context(ds.SOPClassUID)
                abstract_syntax = str(context).splitlines()[0].split(sep=":")[1]
                tree_child_item.setText(0, abstract_syntax)
                self._populate_tree_widget_item_from_dataset(parent=tree_child_item, ds=ds)
                tree_child_item.setExpanded(True)
            finally:
                self.dcm_tree_widget.blockSignals(False)
            self.has_edits = False

    def on_file_save_as(self):
        save_path = self.previous_save_path
        file_name, ok = QFileDialog.getSaveFileName(self, "Save DICOM File", str(save_path), "DICOM Files (*.dcm)")
        if len(file_name) == 0:
            return
        path = Path(file_name)
        self.previous_save_path = path.parent
        self._perform_save(str(path))

    def on_file_save(self):
        file_name = self.current_list_item.text()
        path = Path(file_name)
        self.previous_save_path = path.parent
        self._perform_save(str(path))

    def _perform_save(self, path: str) -> bool:
        """Save, asking first if a value is too long for Explicit VR.

        An edited row whose element cannot be resolved is refused through its pending error, recorded by
        on_tree_item_changed, which _save_dataset_to raises on (#71). Returns True on success, False on refusal.
        """
        choice = OversizedChoice.KEEP_IMPLICIT
        if not self._pending_errors and self._source_is_implicit():
            oversized = self._current_oversized()
            if oversized:
                asked = self._ask_oversized_choice(oversized)
                if asked is None:
                    return False
                choice = asked
        try:
            durable = self._save_dataset_to(Path(path), choice)
        except ValueError as e:
            self.non_native_warning_message("Save refused", str(e), QMessageBox.Ok)
            return False
        self.has_edits = False
        if not durable:
            # Saved, but not confirmed durable: the file was replaced, so this is a warning, never a failure (#85)
            self.non_native_warning_message(
                "Saved, not confirmed durable",
                f"{path} was saved, but the system could not confirm the save is durable. "
                "If the computer loses power soon, the previous version of the file may come back.",
                QMessageBox.Ok,
            )
        return True

    def _save_dataset_to(self, path: Path, oversized_choice: OversizedChoice = OversizedChoice.KEEP_IMPLICIT) -> bool:
        """Write the dataset to path atomically. Never shows a dialog.

        Returns False when the file was written and replaced but the directory fsync failed, so the rename is not
        confirmed durable (#85); True otherwise. Raises ValueError when the save is refused.
        """
        if self._pending_errors:
            msgs = [str(e) for e in self._pending_errors.values()]
            raise ValueError("; ".join(msgs))
        # Prune creators emptied this session (cora 13021 #4) — exact tags, re-check at save
        if self._pruned_creators:
            for creator_tag, ds_ref in self._pruned_creators:
                if ds_ref is self.current_dataset and creator_tag in self.current_dataset:
                    block_byte = creator_tag.element
                    group = creator_tag.group
                    # Re-check the block is still empty (member may have been added)
                    has_members = any(
                        k.group == group and k.element >> 8 == block_byte and k.element != block_byte
                        for k in self.current_dataset.keys()
                    )
                    if not has_members:
                        del self.current_dataset[creator_tag]
            self._pruned_creators.clear()
        # Save from current_dataset, not from the tree (issue #35). The tree is a view;
        # anything it cannot represent (private elements, OB/OW bytes) must survive.
        modified_ds = deepcopy(self.current_dataset)
        modified_ds.ensure_file_meta()
        # Transfer syntax (#57, #79): downstream systems need the VRs, so Implicit VR LE becomes Explicit VR LE, unless a
        # value is too long for Explicit VR; then the user's choice decides. Other source syntaxes are kept.
        ts = modified_ds.file_meta.get("TransferSyntaxUID") if modified_ds.file_meta else None
        has_oversized = self._source_is_implicit() and bool(self._current_oversized())
        new_ts, is_implicit = choose_transfer_syntax(ts, has_oversized, oversized_choice)
        modified_ds.file_meta.TransferSyntaxUID = new_ts
        modified_ds.is_implicit_VR = is_implicit
        if new_ts in (pydicom.uid.ImplicitVRLittleEndian, pydicom.uid.ExplicitVRLittleEndian):
            modified_ds.is_little_endian = True
        # Write the file a symlink points to, not the link: os.replace would swap the link for a regular file and
        # leave its target unchanged (#69). Resolving first keeps the temp file beside the real file, so the
        # replace stays atomic.
        path = path.resolve()
        # Atomic write: temp in same directory, fsync, os.replace (issue #43)
        durable = True
        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                dcmwrite(f, modified_ds, write_like_original=False)
                f.flush()
                os.fsync(f.fileno())
            # Preserve target's permissions (mkstemp creates 0600)
            if path.exists():
                os.chmod(str(tmp_path), path.stat().st_mode & 0o7777)
            else:
                os.chmod(str(tmp_path), 0o666 & ~_get_umask())
            os.replace(str(tmp_path), str(path))
            # fsync the directory — POSIX only (Windows raises after replace)
            if os.name == "posix":
                try:
                    dir_fd = os.open(str(path.parent), os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError as e:
                    logging.warning(f"Directory fsync failed (replace already succeeded): {e}")
                    durable = False
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        return durable

    def _source_is_implicit(self) -> bool:
        """Whether the loaded file is Implicit VR LE, or records no transfer syntax."""
        meta = getattr(self.current_dataset, "file_meta", None)
        ts = meta.get("TransferSyntaxUID") if meta else None
        return not ts or ts == pydicom.uid.ImplicitVRLittleEndian

    def _note_value_length(self, ds: Dataset, tag) -> None:
        """Record an edited or added element if its value is now too long for Explicit VR (#79)."""
        tag = BaseTag(pydicom.tag.Tag(tag))
        if tag in ds and encoded_value_length(ds[tag]) > MAX_SHORT_VALUE_LENGTH:
            if not any(d is ds and t == tag for d, t in self._oversized):
                self._oversized.append((ds, tag))

    @staticmethod
    def _reachable_datasets(ds: Dataset) -> set[int]:
        """ids of ds and every sequence item under it. Only sequences are opened; other values are not converted."""
        ids = {id(ds)}
        for tag in list(ds.keys()):
            elem = ds.get_item(tag)
            vr = _element_vr(tag, elem)
            if vr == "SQ" or (vr is None and isinstance(elem, RawDataElement) and elem.length == 0xFFFFFFFF):
                for item in ds[tag].value:
                    ids |= DCMQtreePy._reachable_datasets(item)
        return ids

    def _current_oversized(self) -> list[tuple[Dataset, BaseTag]]:
        """The recorded elements still in the dataset and still too long for Explicit VR (#79).

        An element in a deleted sequence item is no longer reachable, and an edit may have shortened a value, so only
        the recorded elements are re-measured; nothing else is walked except the sequence structure.
        """
        if not self._oversized:
            return []
        reachable = self._reachable_datasets(self.current_dataset)
        return [
            (d, t)
            for d, t in self._oversized
            if id(d) in reachable and t in d and encoded_value_length(d[t]) > MAX_SHORT_VALUE_LENGTH
        ]

    def _ask_oversized_choice(self, oversized: list[tuple[Dataset, BaseTag]]) -> OversizedChoice | None:
        """Ask how to save values too long for Explicit VR. None means cancel: nothing is written (#79)."""
        names = sorted({f"{t} {pydicom.datadict.keyword_for_tag(t) or 'private'}" for _, t in oversized})
        app = QApplication.instance()
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Question)
        dlg.setWindowTitle("Values too long for Explicit VR")
        dlg.setText(
            f"{len(oversized)} value(s) are longer than 65534 bytes, the most Explicit VR can hold for their VR: "
            + ", ".join(names)
        )
        dlg.setInformativeText(
            "Keep Implicit VR (default): the file carries no VRs. Private VRs then depend on the reader's dictionary, "
            "and the file cannot be compressed or exported to media.\n\n"
            "Explicit VR with UN: every other element keeps its VR. The listed elements are written as UN "
            "(PS3.5 6.2.2), so a reader must know their VR to decode them; pydicom 2.4.5, and so this application, "
            "reads them back as raw bytes."
        )
        keep = dlg.addButton("Keep Implicit VR", QMessageBox.ButtonRole.AcceptRole)
        explicit_un = dlg.addButton("Explicit VR with UN", QMessageBox.ButtonRole.AcceptRole)
        dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(keep)
        dlg.setProperty("help_id", "warnings")
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked is keep:
            return OversizedChoice.KEEP_IMPLICIT
        if clicked is explicit_un:
            return OversizedChoice.EXPLICIT_WITH_UN
        return None

    def on_add_element(self):
        add_element_dialog = AddPublicElementDialog(self)
        add_element_dialog.setProperty("help_id", "add_public_element_dialog")
        add_element_dialog.exec()
        public_element = add_element_dialog.current_public_element
        if public_element is None:
            return
        vr_as_string = public_element.VR
        plain_text = add_element_dialog.ui.text_edit_element_value.toPlainText()
        element_value = None
        if plain_text is not None and len(plain_text) > 0:
            value_list = self._convert_text_lines_to_vr_values(plain_text, vr_as_string)
            if len(value_list) == 0:
                element_value = None
                self.non_native_warning_message(
                    "Invalid Value", "Value can not be converted to expected VR, using empty value", QMessageBox.Ok
                )

            elif len(value_list) == 1:
                element_value = value_list[0]
            else:
                element_value = value_list

        public_element.value = element_value
        # Resolve target dataset (connor: single function)
        target_ds = self.current_dataset
        if self.dcm_tree_widget is not None:
            selected_items = self.dcm_tree_widget.selectedItems()
            if selected_items is not None and len(selected_items) > 0:
                target_ds = self._resolve_add_target(selected_items[0])
                if target_ds is None:
                    self.non_native_warning_message(
                        "Add refused",
                        "An element cannot be added directly to a sequence header. Select an item or element row.",
                        QMessageBox.Ok,
                    )
                    return
        target_ds[public_element.tag] = public_element
        self._note_value_length(target_ds, public_element.tag)
        # The dataset changed, whatever was selected (#63).
        self.has_edits = True
        parent = self._add_parent_row()
        if parent is not None:
            self._populate_tree_widget_item_from_element(parent, public_element)
            parent.sortChildren(0, Qt.AscendingOrder)

    def _add_parent_row(self) -> QTreeWidgetItem | None:
        """The tree row that a newly added element is shown under.

        With a row selected: an item or sequence row (empty or SQ VR) itself, otherwise the selected row's parent.
        With nothing selected the element went into the root dataset, so it is shown under the root row (#63).
        None when no file is loaded.
        """
        if self.dcm_tree_widget is None:
            return None
        selected_items = self.dcm_tree_widget.selectedItems()
        if selected_items:
            selected_item = selected_items[0]
            vr_as_string = selected_item.text(3)
            if len(vr_as_string) == 0 or vr_as_string == "SQ":
                return selected_item
            return selected_item.parent()
        return self.dcm_tree_widget.topLevelItem(0)

    def on_add_private_element(self):
        add_element_dialog = AddPrivateElementDialog(self)
        add_element_dialog.setProperty("help_id", "add_private_element_dialog")

        add_element_dialog.exec()
        if add_element_dialog.current_private_block is None:
            return
        block = add_element_dialog.current_private_block
        # private_creator = block.private_creator
        # group = block.group
        private_element = add_element_dialog.current_private_block[add_element_dialog.current_byte_offset]
        if private_element is None:
            return
        vr_as_string = private_element.VR
        plain_text = add_element_dialog.ui.text_edit_element_value.toPlainText()
        element_value = None
        if plain_text is not None and len(plain_text) > 0:
            value_list = self._convert_text_lines_to_vr_values(plain_text, vr_as_string)
            if len(value_list) == 0:
                element_value = None
                self.non_native_warning_message(
                    "Invalid Value", "Value can not be converted to expected VR, using empty value", QMessageBox.Ok
                )
            elif len(value_list) == 1:
                element_value = value_list[0]
            else:
                element_value = value_list
        private_element.value = element_value
        # Resolve target dataset (connor: single function)
        target_ds = self.current_dataset
        if self.dcm_tree_widget is not None:
            selected_items = self.dcm_tree_widget.selectedItems()
            if selected_items is not None and len(selected_items) > 0:
                target_ds = self._resolve_add_target(selected_items[0])
                if target_ds is None:
                    self.non_native_warning_message(
                        "Add refused",
                        "An element cannot be added directly to a sequence header. Select an item or element row.",
                        QMessageBox.Ok,
                    )
                    return
        # The dialog built its block on a scratch dataset, so its tags assume creator slot 0x10. Resolve the block in the
        # target dataset instead: that finds an existing creator or reserves the next free slot, and the creator element
        # goes into the dataset with the member. The tree follows the dataset (#63).
        slot = self._private_creator_slot(target_ds, block.group, block.private_creator)
        if slot is None:
            self.non_native_warning_message(
                "Add refused",
                f"Group {block.group:04X} has no free private creator slot (0010-00FF are all in use).",
                QMessageBox.Ok,
            )
            return
        creator_element = target_ds[pydicom.tag.Tag(block.group, slot)]
        member_tag = pydicom.tag.Tag(block.group, (slot << 8) | add_element_dialog.current_byte_offset)
        target_ds.add_new(member_tag, private_element.VR, private_element.value)
        self._note_value_length(target_ds, member_tag)
        member_element = target_ds[member_tag]
        # The dataset changed, whatever was selected (#63).
        self.has_edits = True
        parent = self._add_parent_row()
        if parent is not None:
            shown_tags = {
                pydicom.tag.Tag(self._convert_tag_as_string_to_tuple(parent.child(x).text(0)))
                for x in range(parent.childCount())
            }
            if creator_element.tag not in shown_tags:
                self._populate_tree_widget_item_from_element(parent, creator_element)
            self._populate_tree_widget_item_from_element(parent, member_element)
            parent.sortChildren(0, Qt.AscendingOrder)

    @staticmethod
    def _private_creator_slot(ds: pydicom.Dataset, group: int, creator: str) -> int | None:
        """The element byte (0x10-0xFF) of creator's block in ds, reserving the first free slot if it has none.

        Returns None if all 240 slots hold other creators. pydicom's Dataset.private_block() is not used: in pydicom
        2.4.5 its cached block makes deepcopy of a dataset read from file recurse without end, and save deep-copies.
        """
        free = None
        for slot in range(0x10, 0x100):
            elem = ds.get(pydicom.tag.Tag(group, slot))
            if elem is None:
                if free is None:
                    free = slot
            elif elem.value == creator:
                return slot
        if free is not None:
            ds.add_new((group, free), "LO", creator)
        return free

    @Slot()
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            # e.accept()

    @Slot()
    def dropEvent(self, event):
        mime_data = event.mimeData()
        url_list = mime_data.urls()
        my_file_name_list = [x.toLocalFile() for x in url_list]
        for my_file_name in my_file_name_list:
            file_list_item = QListWidgetItem(str(my_file_name))
            self.ui.listWidget.addItem(file_list_item)
        event.acceptProposedAction()

    @Slot()
    def handle_file_list_delete_pressed(self, event):
        current_row = self.ui.listWidget.currentRow()
        if self.has_edits:
            button = self.non_native_warning_message(
                "Current Tree Has Edits", "Continuing will lose current edits", buttons=QMessageBox.Ok | QMessageBox.Cancel
            )
            if button == QMessageBox.Cancel:
                return
            else:
                self.has_edits = False  # or at least behave as if it was

        self.ui.listWidget.takeItem(current_row)

    @Slot()
    def on_tree_item_changed(self, item: QTreeWidgetItem, column: int):
        if column != 2:
            return
        tag_as_string = item.text(0)
        tag = self._convert_tag_as_string_to_tuple(tag_as_string)
        new_value = item.text(2)
        # Resolve the row's own dataset from its ancestor chain (cora 13021 #1)
        parent_ds, _, _, _ = self._find_parent_dataset(item)
        try:
            elem = parent_ds[pydicom.tag.Tag(tag)]
            if elem.VR in BINARY_VRS:
                # A byte payload has no text form here: put the cell back and leave the value alone (#64)
                was_blocked = self.dcm_tree_widget.blockSignals(True)
                try:
                    item.setText(2, self._value_cell_text(elem))
                finally:
                    self.dcm_tree_widget.blockSignals(was_blocked)
                self.non_native_warning_message(
                    "Edit refused", f"{tag_as_string} is {elem.VR}: a binary value cannot be edited as text.", QMessageBox.Ok
                )
                return
            if elem.VR != "SQ":
                elem.value = self._parse_value_cell_text(new_value, elem.VR)
                self._note_value_length(parent_ds, tag)
            # Clear per-row error on success (cora: correcting a bad edit unblocks save)
            self._pending_errors.pop(id(item), None)
        except (KeyError, ValueError) as e:
            self._pending_errors[id(item)] = ValueError(f"{tag_as_string}: {e}")
            pass
        self.has_edits = True

    def _drop_pending_errors_for_subtree(self, item: QTreeWidgetItem) -> None:
        """Drop pending errors for a row and all its descendants (cora: removed subtrees)."""
        self._pending_errors.pop(id(item), None)
        for i in range(item.childCount()):
            self._drop_pending_errors_for_subtree(item.child(i))

    def _resolve_add_target(self, item: QTreeWidgetItem):
        """Return the dataset where new children of this row belong.
        Item row → that item's dataset. Element row → the row's dataset.
        Sequence header → None (an element can't sit directly in a sequence).
        (connor: single function, matching the tree's own rule)
        """
        # Sequence header (not an item): refuse (cora: element can't sit in a sequence)
        if item.text(3) == "SQ" and not item.text(2).isdigit():
            return None
        parent = item.parent()
        if parent is None:
            return self.current_dataset
        parent_tag_str = parent.text(0)
        if "(" not in parent_tag_str:
            return self.current_dataset
        # Item row: tag matches parent + numeric value
        if item.text(2).isdigit() and item.text(0) == parent.text(0):
            parent_ds, is_sq, seq_tag, item_idx = self._find_parent_dataset(item)
            if is_sq and seq_tag is not None:
                seq_elem = parent_ds.get(pydicom.tag.Tag(seq_tag))
                if seq_elem is not None and seq_elem.VR == "SQ" and 0 <= item_idx < len(seq_elem.value):
                    return seq_elem.value[item_idx]
            return self.current_dataset
        # Element row: the dataset that holds this element
        parent_ds, _, _, _ = self._find_parent_dataset(item)
        return parent_ds

    def _find_parent_dataset(self, item: QTreeWidgetItem):
        """Walk up the tree to find the Dataset that holds this element.
        Returns (parent_ds, is_sequence_item, seq_tag, item_index).
        """
        parent = item.parent()
        if parent is None:
            return self.current_dataset, False, None, None
        parent_tag_str = parent.text(0)
        if "(" not in parent_tag_str:
            return self.current_dataset, False, None, None
        parent_tag = self._convert_tag_as_string_to_tuple(parent_tag_str)
        # If the item itself is a sequence item (tag matches parent + numeric value)
        if item.text(2).isdigit() and item.text(0) == parent.text(0):
            seq_tag = parent_tag
            # Resolve the dataset that owns this sequence (cora: nested seq-item)
            owner_ds = self._find_sequence_owner(parent)
            seq_elem = owner_ds.get(pydicom.tag.Tag(seq_tag))
            if seq_elem is not None and seq_elem.VR == "SQ":
                # The item's position under its header, never its displayed number, which a delete leaves stale (#65).
                item_idx = parent.indexOfChild(item)
                return owner_ds, True, seq_tag, item_idx
            return self.current_dataset, False, None, None
        # Climb through nested sequence items recursively
        current = item
        current_parent = item.parent()
        while current_parent is not None:
            current_tag_str = current_parent.text(0)
            if "(" not in current_tag_str:
                break
            if current.text(2).isdigit() and current.text(0) == current_parent.text(0):
                # current is a sequence item under current_parent (sequence header)
                seq_tag = self._convert_tag_as_string_to_tuple(current_tag_str)
                # Find the dataset that owns this sequence by climbing further
                owner_ds = self._find_sequence_owner(current_parent)
                seq_elem = owner_ds.get(pydicom.tag.Tag(seq_tag))
                if seq_elem is not None and seq_elem.VR == "SQ":
                    item_idx = current_parent.indexOfChild(current)  # position, not displayed number (#65)
                    if 0 <= item_idx < len(seq_elem.value):
                        return seq_elem.value[item_idx], True, seq_tag, item_idx
                return self.current_dataset, False, None, None
            current = current_parent
            current_parent = current_parent.parent()
        return self.current_dataset, False, None, None

    def _find_sequence_owner(self, header_item: QTreeWidgetItem):
        """Find the Dataset that owns a sequence header row."""
        parent = header_item.parent()
        if parent is None:
            return self.current_dataset
        parent_tag_str = parent.text(0)
        if "(" not in parent_tag_str:
            return self.current_dataset
        # If parent is a sequence item, recurse
        if header_item.text(2).isdigit() and header_item.text(0) == parent.text(0):
            return self._find_sequence_owner(parent)
        # Climb through nested items
        current = header_item
        current_parent = header_item.parent()
        while current_parent is not None:
            ct_str = current_parent.text(0)
            if "(" not in ct_str:
                break
            if current.text(2).isdigit() and current.text(0) == current_parent.text(0):
                seq_tag = self._convert_tag_as_string_to_tuple(ct_str)
                owner = self._find_sequence_owner(current_parent)
                seq_elem = owner.get(pydicom.tag.Tag(seq_tag))
                if seq_elem is not None and seq_elem.VR == "SQ":
                    item_idx = current_parent.indexOfChild(current)  # position, not displayed number (#65)
                    if 0 <= item_idx < len(seq_elem.value):
                        return seq_elem.value[item_idx]
                return self.current_dataset
            current = current_parent
            current_parent = current_parent.parent()
        return self.current_dataset

    def handle_tree_delete_pressed(self, event):
        if self.dcm_tree_widget is not None:
            selected_items = self.dcm_tree_widget.selectedItems()
            if selected_items is not None and len(selected_items) > 0:
                selected_item = selected_items[0]
                parent = selected_item.parent()
                child_index = parent.indexOfChild(selected_item)

                tag_as_string = selected_item.text(0)
                tag = self._convert_tag_as_string_to_tuple(tag_as_string)
                if tag[0] % 2 == 1:
                    private_block_byte = tag[1] % 256
                    if tag[1] >= 0x0010 and tag[1] <= 0x00FF:
                        # Resolve the row's own dataset (cora: nested creator delete)
                        parent_ds, _, _, _ = self._find_parent_dataset(selected_item)
                        next_child = parent.child(child_index + 1)
                        if next_child is not None:
                            tag_as_string2 = next_child.text(0)
                            tag2 = self._convert_tag_as_string_to_tuple(tag_as_string2)
                            if tag2[0] % 2 == 1:
                                # Delete only members of THIS block (same group + block byte)
                                for j in range(parent.childCount() - 1, child_index, -1):
                                    member = parent.child(j)
                                    member_tag = self._convert_tag_as_string_to_tuple(member.text(0))
                                    if member_tag[0] == tag[0] and member_tag[1] >> 8 == private_block_byte:
                                        try:
                                            del parent_ds[pydicom.tag.Tag(member_tag)]
                                            self._drop_pending_errors_for_subtree(member)
                                            parent.takeChild(j)
                                        except KeyError:
                                            self.non_native_warning_message(
                                                "Delete failed",
                                                f"Element {member.text(0)} not found in dataset.",
                                                QMessageBox.Ok,
                                            )
                                            return
                                # Delete the creator element itself
                                try:
                                    del parent_ds[pydicom.tag.Tag(tag)]
                                    self._drop_pending_errors_for_subtree(selected_item)
                                except KeyError:
                                    self.non_native_warning_message(
                                        "Delete failed",
                                        f"Creator {tag_as_string} not found in dataset.",
                                        QMessageBox.Ok,
                                    )
                                    return
                                parent.takeChild(child_index)
                                self.has_edits = True
                                return
                # Sequence items share their parent tag and have numeric text(2)
                is_seq_item = selected_item.text(2).isdigit() and selected_item.text(0) == parent.text(0)
                if is_seq_item:
                    # Deleting a sequence item — resolve owner dataset (cora: nested seq-item)
                    parent_ds, is_sq, seq_tag, item_idx = self._find_parent_dataset(selected_item)
                    if is_sq and seq_tag is not None:
                        seq_elem = parent_ds.get(pydicom.tag.Tag(seq_tag))
                        if seq_elem is not None and seq_elem.VR == "SQ":
                            del seq_elem.value[item_idx]
                            self._drop_pending_errors_for_subtree(selected_item)
                else:
                    # Deleting a regular element
                    parent_ds, _, _, _ = self._find_parent_dataset(selected_item)
                    # Refuse unresolvable private elements (cora 13021 #3)
                    if tag[0] % 2 == 1 and tag[1] >= 0x0100:
                        block_byte = tag[1] >> 8
                        creator_tag = pydicom.tag.Tag(tag[0], block_byte)
                        if creator_tag not in parent_ds:
                            self.non_native_warning_message(
                                "Delete refused",
                                f"Element {tag_as_string} has no private creator — cannot safely delete.",
                                QMessageBox.Ok,
                            )
                            return
                    try:
                        del parent_ds[pydicom.tag.Tag(tag)]
                        self._drop_pending_errors_for_subtree(selected_item)
                        # Cyril 2026-11-01: keep empty items — do NOT prune here
                        # Track emptied private blocks for creator prune (cora 13021 #4)
                        # Only track root-level creators — nested items may share names
                        if tag[0] % 2 == 1 and tag[1] >= 0x0100 and parent_ds is self.current_dataset:
                            block_byte = tag[1] >> 8
                            creator_tag = pydicom.tag.Tag(tag[0], block_byte)
                            if creator_tag in parent_ds:
                                # Check if block is now empty
                                has_members = False
                                for k in parent_ds.keys():
                                    if k.group == tag[0] and k.element >> 8 == block_byte and k.element != block_byte:
                                        has_members = True
                                        break
                                if not has_members:
                                    self._pruned_creators.append((creator_tag, parent_ds))
                    except KeyError:
                        self.non_native_warning_message(
                            "Delete failed",
                            f"Element {tag_as_string} not found in dataset.",
                            QMessageBox.Ok,
                        )
                        return
                parent.takeChild(child_index)
                if is_seq_item:
                    self._renumber_item_rows(parent)
                self.has_edits = True

    def _renumber_item_rows(self, header: QTreeWidgetItem) -> None:
        """Show each remaining item under a sequence header with its 1-based position (#65).

        Resolution already uses the row's position, so this is what the user reads. Signals are blocked so the
        rewrite is not taken as an edit.
        """
        blocked = self.dcm_tree_widget.blockSignals(True)
        try:
            for i in range(header.childCount()):
                header.child(i).setText(2, str(i + 1))
        finally:
            self.dcm_tree_widget.blockSignals(blocked)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key.Key_F1:
            # Check if we have a current menu action
            if self.current_menu_action:
                help_id = self.current_menu_action.property("help_id")
                if help_id:
                    self.logger.debug(f"Showing help for menu action: {self.current_menu_action.text()}, help_id: {help_id}")
                    self.help_assistant.show_help_topic(help_id)
                    return True
            # Check if this is coming from a menu
            if isinstance(obj, QMenu) or isinstance(obj, QAction):
                help_id = obj.property("help_id")
                if help_id:
                    self.help_assistant.show_help_topic(help_id)
                    return True
                # If the menu item doesn't have a help_id, check its parent menu
                elif hasattr(obj, "parent") and obj.parent():
                    help_id = obj.parent().property("help_id")
                    if help_id:
                        self.help_assistant.show_help_topic(help_id)
                        return True

            # If we couldn't find context-specific help, fall back to the general handler
            self.show_context_help()
            return True

        # For all other events, let the default handler take care of it
        return super().eventFilter(obj, event)

    @Slot()
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            print("Delete key was pressed")
        elif event.key() == Qt.Key.Key_F1:
            # Instead of directly calling show_context_help, check if a menu is active
            menu_widget = QApplication.activePopupWidget()
            if menu_widget and isinstance(menu_widget, QMenu):
                if action := menu_widget.activeAction():
                    if help_id := action.property("help_id"):
                        self.help_assistant.show_help_topic(help_id)
                        event.accept()
                        return

            # If we get here, either no menu is active or no help_id was found
            # Fall back to regular context help
            self.show_context_help()
            event.accept()
        else:
            # For other keys, let the parent class handle it
            super().keyPressEvent(event)

    def non_native_warning_message(self, title: str = "Warning Message", text: str = "", buttons=None) -> QMessageBox.button:
        app = QApplication.instance()
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)

        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Warning)
        if text is None:
            msg_text = " failed. Please check log for more information"
        else:
            msg_text = text
        dlg.setText(msg_text)
        dlg.setWindowTitle(title)
        dlg.setStandardButtons(buttons)
        dlg.setProperty("help_id", "warnings")
        button = dlg.exec()
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, False)
        return button

    def show_context_help(self):
        """
        Display context-sensitive help based on the currently focused widget.
        Traverses the widget hierarchy to find the nearest widget with help context.
        """
        if active_popup := QApplication.activePopupWidget():
            self.logger.debug(f"Active popup: {active_popup.__class__.__name__}")

            # Handle QMenu popups specially
            if isinstance(active_popup, QMenu):
                action = active_popup.activeAction()
                if action and action.property("help_id"):
                    help_id = action.property("help_id")
                    self.logger.debug(f"Showing help for menu action: {action.text()}, topic: {help_id}")
                    self.help_assistant.show_help_topic(help_id)
                    return

        if current_widget := QApplication.focusWidget():
            property_value, widget_with_help = self.find_help_id_widget(current_widget)
            if property_value is not None:
                self.logger.debug(f"help_id for {widget_with_help} is {property_value}")
                self.help_assistant.show_help_topic(property_value)
            else:
                self.logger.error(f"No help_id found in widget hierarchy starting from: {current_widget.__class__.__name__}")
                # Fall back to general help if no specific help is defined
                self.help_assistant.show_help_topic("dicom")
        else:
            self.logger.debug("No widget currently has focus")
            self.help_assistant.show_help_topic("dicom")

    def find_help_id_widget(self, widget):
        """
        Traverse up the widget hierarchy starting from the given widget
        until finding a widget with a help_id property.

        Args:
            widget (QWidget): The starting widget (typically one with focus)

        Returns:
            tuple: (help_id, widget) if found, (None, None) if not found
        """
        current = widget
        while current is not None:
            help_id = current.property("help_id")
            print(f"Checking {current.__class__.__name__} named '{current.objectName()}' - help_id: {help_id}")

            # If we're in a menu or menu bar system
            if isinstance(current, (QMenu, QMenuBar)):
                for action in current.actions():
                    action_help_id = action.property("help_id")
                    print(f"  Menu action '{action.text()}' - help_id: {action_help_id}")
                    if action_help_id is not None:
                        return action_help_id, action

            print(f"Searching for widget with help_id property: looking at {current}")
            if current.property("help_id") is not None:
                return current.property("help_id"), current
            current = current.parent()
        return None, None

    def closeEvent(self, event):
        # Clean up the assistant process
        self.help_assistant.cleanup()
        # Call the existing closeEvent logic
        super().closeEvent(event)


def main():
    if "--selftest" in sys.argv:
        # Hidden CI entry point (dcmqtreepy/selftest.py): dispatch BEFORE QApplication
        # and window construction so the packaged GUI never opens on a headless runner.
        # Refs #33/#34 — packaged smoke: open a sample DICOM, save it byte-identical,
        # render it in the bundled viewer, exit 0 only if every stage passed.
        from dcmqtreepy.selftest import selftest_main

        rest = [a for a in sys.argv[1:] if a != "--selftest"]
        sys.exit(selftest_main(rest))
    app = QApplication(sys.argv)
    widget = DCMQtreePy()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    # Set up logging to file
    user_home = Path.home()
    log_path = Path(platformdirs.user_log_dir("dcmQTreePy"))  # user_home / "Library" / "Logs" / "dcmQTreePy"
    Path(log_path).mkdir(parents=True, exist_ok=True)
    log_file = log_path.joinpath("dcmQTreePy.log")

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),  # Keep console output as well
        ],
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Logging to {log_file}")
    main()
