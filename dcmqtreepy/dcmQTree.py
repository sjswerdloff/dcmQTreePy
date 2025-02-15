#!/usr/bin/env python
# This Python file uses the following encoding: utf-8

import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List

import pydicom
import pydicom.config
import pydicom.datadict
import pydicom.dataset
import pydicom.valuerep
import tomli
from pydicom import DataElement, Dataset, Sequence, dcmread, dcmwrite
from pydicom.valuerep import VR
from pynetdicom.presentation import build_context
from PySide6.QtCore import QDateTime, Qt, Slot  # pylint: disable=no-name-in-module
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QApplication,
    QFileDialog,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QWidget,
)

from dcmqtreepy import impac_privates
from dcmqtreepy.add_private_element_dialog import AddPrivateElementDialog
from dcmqtreepy.add_public_element_dialog import AddPublicElementDialog
from dcmqtreepy.mainwindow import Ui_MainWindow
from dcmqtreepy.new_privates import new_private_dictionaries


class DCMQtreePy(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()

        self.ui.setupUi(self)

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
        self.previous_path = Path().home()
        self.previous_save_path = Path().home()
        self.current_list_item = None
        self.reverting_list_item = False
        self.current_dataset = Dataset()
        self.has_edits = False
        pydicom.config.Settings.writing_validation_mode = pydicom.config.RAISE
        for creator, private_dict in new_private_dictionaries.items():
            try:
                pydicom.datadict.add_private_dict_entries(creator, private_dict)
                logging.warning(f"Private dictionary for {creator} has been loaded")
            except ValueError:
                logging.error(f"Unable to load private dictionary for {creator}")

        # pydicom.datadict.add_private_dict_entries("IMPAC", impac_privates.impac_private_dict)

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
        cast_values = list()
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
                return list()
            cast_values.append(cast_value)
        return cast_values

    def _convert_tag_as_string_to_tuple(self, tag_as_string: str) -> tuple[int, int]:
        first_split = tag_as_string.split("(")[1]
        group = first_split.split(",")[0]
        elem_hex_as_string = first_split.split(",")[1].split(")")[0]
        return (int(group, 16), int(elem_hex_as_string, 16))

    def _isEditable(self, column: int) -> bool:
        if column == 2:
            return True
        else:
            return False

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

    @Slot()
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            print("Delete key was pressed")

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
        button = dlg.exec()
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, False)
        return button


def main():
    app = QApplication(sys.argv)
    widget = DCMQtreePy()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
