#!/usr/bin/env python
# This Python file uses the following encoding: utf-8
import atexit
import logging
import os
import sys
from decimal import Decimal
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
    QTreeWidgetItemIterator,
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


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


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

    def _populate_tree_widget_item_from_element(self, parent: QTreeWidgetItem | QTreeWidget, elem: DataElement):
        if elem.VR != VR.SQ:
            tree_child_item = QTreeWidgetItem(parent)
            tree_child_item.setFlags(Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            tree_child_item.setText(0, str(elem.tag))
            tree_child_item.setText(1, elem.name)
            if elem.VR not in [VR.OB, VR.OW, VR.OB_OW, VR.OD, VR.OF]:
                if elem.value is None:
                    tree_child_item.setText(2, "")
                else:
                    tree_child_item.setText(2, str(elem.value))
            else:
                logging.warning("Need to stash away OB/OW type values")
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
                tree_child_item.setFlags(Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tree_child_item.setText(0, str(elem.tag))
                tree_child_item.setText(1, elem.name)
                if elem.VR not in [VR.OB, VR.OW, VR.OB_OW, VR.OD, VR.OF]:
                    if elem.value is None:
                        tree_child_item.setText(2, "")
                    else:
                        tree_child_item.setText(2, str(elem.value))
                else:
                    logging.warning("Need to stash away OB/OW type values")
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
            # ds.remove_private_tags() # temporarily, until save as is working.
            self.current_dataset = ds
            self.dcm_tree_widget.clear()
            tree_child_item = QTreeWidgetItem(self.dcm_tree_widget)
            context = build_context(ds.SOPClassUID)
            abstract_syntax = str(context).splitlines()[0].split(sep=":")[1]
            tree_child_item.setText(0, abstract_syntax)
            self._populate_tree_widget_item_from_dataset(parent=tree_child_item, ds=ds)
            tree_child_item.setExpanded(True)
            self.has_edits = False

    def on_file_save_as(self):
        save_path = self.previous_save_path
        file_name, ok = QFileDialog.getSaveFileName(self, "Save DICOM File", str(save_path), "DICOM Files (*.dcm)")
        if len(file_name) == 0:
            return
        path = Path(file_name)
        self.previous_save_path = path.parent
        iterator = QTreeWidgetItemIterator(self.dcm_tree_widget)
        tree_child_item = iterator.__next__().value()
        modified_ds = Dataset()

        # modified_ds.is_little_endian = True

        for child_index in range(tree_child_item.childCount()):
            child = tree_child_item.child(child_index)
            self._populate_dataset_from_tree_widget_item(parent_ds=modified_ds, tree_widget_item=child)

        if "PixelData" in self.current_dataset:
            modified_ds["PixelData"] = self.current_dataset["PixelData"]
        # modified_ds.fix_meta_info(enforce_standard=False)
        modified_ds.ensure_file_meta()
        #
        modified_ds.is_implicit_VR = False
        modified_ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
        # del modified_ds[0x300a0782]
        # modified_ds.remove_private_tags() # temporary... first get save as working for public elements
        dcmwrite(Path(file_name), modified_ds, write_like_original=False)
        self.has_edits = False  # not quite true, but the data has been saved, so switching and losing the current edits is OK.

    def on_file_save(self):
        file_name = self.current_list_item.text()
        path = Path(file_name)
        self.previous_save_path = path.parent
        iterator = QTreeWidgetItemIterator(self.dcm_tree_widget)
        tree_child_item = iterator.__next__().value()
        modified_ds = Dataset()

        # modified_ds.is_little_endian = True

        for child_index in range(tree_child_item.childCount()):
            child = tree_child_item.child(child_index)
            self._populate_dataset_from_tree_widget_item(parent_ds=modified_ds, tree_widget_item=child)

        if "PixelData" in self.current_dataset:
            modified_ds["PixelData"] = self.current_dataset["PixelData"]
        # modified_ds.fix_meta_info(enforce_standard=False)
        modified_ds.ensure_file_meta()
        #
        modified_ds.is_implicit_VR = False
        modified_ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
        # del modified_ds[0x300a0782]
        # modified_ds.remove_private_tags() # temporary... first get save as working for public elements
        dcmwrite(Path(file_name), modified_ds, write_like_original=False)
        self.has_edits = False  # not quite true, but the data has been saved, so switching and losing the current edits is OK.

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
        if self.dcm_tree_widget is not None:
            selected_items = self.dcm_tree_widget.selectedItems()
            if selected_items is not None and len(selected_items) > 0:
                selected_item = selected_items[0]
                vr_as_string = selected_item.text(3)
                if len(vr_as_string) == 0 or vr_as_string == "SQ":
                    parent = selected_item
                else:
                    parent = selected_item.parent()
                self._populate_tree_widget_item_from_element(parent, public_element)
                parent.sortChildren(0, Qt.AscendingOrder)
                self.has_edits = True

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
        if self.dcm_tree_widget is not None:
            selected_items = self.dcm_tree_widget.selectedItems()
            if selected_items is not None and len(selected_items) > 0:
                selected_item = selected_items[0]
                vr_as_string = selected_item.text(3)
                if len(vr_as_string) == 0 or vr_as_string == "SQ":
                    parent = selected_item
                else:
                    parent = selected_item.parent()
                parent.childCount()

                children_tuples = [
                    self._convert_tag_as_string_to_tuple(parent.child(x).text(0)) for x in range(parent.childCount())
                ]
                is_private_block_already_present = False
                for child_tuple in children_tuples:
                    if child_tuple[0] == block.group and child_tuple[1] == 0x10:
                        is_private_block_already_present = True

                if not is_private_block_already_present:
                    private_creator_element = DataElement((block.group, 0x10), "LO", block.private_creator)
                    self._populate_tree_widget_item_from_element(parent, private_creator_element)
                self._populate_tree_widget_item_from_element(parent, private_element)
                parent.sortChildren(0, Qt.AscendingOrder)
                self.has_edits = True

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
                    private_block_byte = tag[1] % 256  # lower 8 bits...
                    if private_block_byte == 0x10:
                        # is_private_creator = True
                        next_child = parent.child(child_index + 1)
                        tag_as_string = next_child.text(0)
                        tag = self._convert_tag_as_string_to_tuple(tag_as_string)
                        if tag[0] % 2 == 1:
                            self.non_native_warning_message(
                                "Private Block has private elements",
                                "Delete private elements in block before deleting Private Creator",
                                buttons=QMessageBox.Ok,
                            )
                            return
                parent.takeChild(child_index)
                self.has_edits = True

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
