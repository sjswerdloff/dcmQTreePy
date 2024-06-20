# This Python file uses the following encoding: utf-8
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pydicom
import tomli
from mainwindow import Ui_MainWindow
from pydicom import DataElement, Dataset, Sequence, dcmread
from pydicom.valuerep import VR
from pynetdicom.presentation import build_context
from PySide6.QtCore import QDateTime, Qt, Slot  # pylint: disable=no-name-in-module
from PySide6.QtWidgets import (  # pylint: disable=no-name-in-module
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)


class DCMQtreePy(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.dcm_tree_widget = self.ui.treeWidget
        self.dcm_tree_widget.editTriggers = self.dcm_tree_widget.EditTrigger.NoEditTriggers
        self.dcm_tree_widget.itemDoubleClicked.connect(self.on_tree_widget_item_double_clicked)
        filepath = sys.argv[1]
        ds = dcmread(filepath, force=True)

        tree_child_item = QTreeWidgetItem(self.dcm_tree_widget)
        context = build_context(ds.SOPClassUID)
        abstract_syntax = str(context).splitlines()[0].split(sep=":")[1]
        tree_child_item.setText(0, abstract_syntax)
        self._populate_tree_widget_item_from_dataset(parent=tree_child_item, ds=ds)
        #   self.dcm_tree_widget.resizeColumnToContents(0)
        #   self.dcm_tree_widget.resizeColumnToContents(1)
        #   self.dcm_tree_widget.resizeColumnToContents(2)
        modified_ds = Dataset()

        for child_index in range(tree_child_item.childCount()):
            child = tree_child_item.child(child_index)
            self._populate_dataset_from_tree_widget_item(parent_ds=modified_ds, tree_widget_item=child)
        print(modified_ds)

    def _populate_tree_widget_item_from_dataset(self, parent: QTreeWidgetItem | QTreeWidget, ds: Dataset):
        for elem in ds:
            if elem.VR != VR.SQ:
                tree_child_item = QTreeWidgetItem(parent)
                tree_child_item.setFlags(Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tree_child_item.setText(0, str(elem.tag))
                tree_child_item.setText(1, elem.name)
                tree_child_item.setText(2, str(elem.value))
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

    def _populate_dataset_from_tree_widget_item(self, parent_ds: Dataset | Sequence | list, tree_widget_item: QTreeWidgetItem):
        tag_as_string = tree_widget_item.text(0)
        name_as_string = tree_widget_item.text(1)
        value_as_string = tree_widget_item.text(2)
        vr_as_string = tree_widget_item.text(3)
        tag = self._convert_tag_as_string_to_tuple(tag_as_string)
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
                    self._populate_dataset_from_tree_widget_item(parent_ds=seq_elem, tree_widget_item=child)
            else:
                item_number = int(value_as_string)
                child_ds = Dataset()
                my_list = parent_ds.value
                my_list.append(child_ds)
                for child_index in range(tree_widget_item.childCount()):
                    child = tree_widget_item.child(child_index)
                    self._populate_dataset_from_tree_widget_item(parent_ds=child_ds, tree_widget_item=child)

        else:
            if len(value_as_string) > 0 and value_as_string[0] == "[":
                my_list_of_values = value_as_string.split("[")[1].split("]")[0].split(",")
                elem = DataElement(tag=tag, VR=vr_as_string, value=my_list_of_values)
            else:
                elem = DataElement(tag=tag, VR=vr_as_string, value=value_as_string)
            parent_ds.add(elem)

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

    @Slot()
    def on_tree_widget_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        if self._isEditable(column):
            self.dcm_tree_widget.editItem(item, column)
        else:
            print(f"Column {column} is not editable")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = DCMQtreePy()
    widget.show()
    sys.exit(app.exec())
