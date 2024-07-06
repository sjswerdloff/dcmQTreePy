import logging

from pydicom import DataElement, Dataset, _private_dict, datadict, dataset
from pydicom.valuerep import VR
from PySide6.QtWidgets import QDialog

from dcmqtreepy.ui_add_private_element_dialog import Ui_add_private_element_dialog


class AddPrivateElementDialog(QDialog, Ui_add_private_element_dialog):
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowTitle("Add Private Element")
        self.ui = Ui_add_private_element_dialog()
        self.ui.setupUi(self)
        self.ui.line_edit_group_hex.editingFinished.connect(self._group_hex_editing_finished)
        self.ui.line_edit_element_hex.editingFinished.connect(self._element_hex_editing_finished)

        self.current_private_dataset = None
        self.current_private_block = None
        self.current_byte_offset = None
        private_creator_sequence = _private_dict.private_dictionaries.keys()
        private_creator_list = list(private_creator_sequence)
        private_creator_list.sort()
        self.ui.combo_box_creator_list.addItems(private_creator_list)

    def _convert_text_lines_to_vr_values(self, text_lines: str, vr_as_string: str) -> list:
        text_list = text_lines.splitlines()
        cast_values = list()
        for value_as_string in text_list:
            try:
                cast_value = value_as_string
                if len(value_as_string) > 0:
                    if vr_as_string in [VR.SS, VR.US]:
                        cast_value = int(value_as_string)
                    elif vr_as_string in [VR.FL, VR.FD]:
                        cast_value = float(value_as_string)
                elif vr_as_string in [VR.SS, VR.US, VR.FL, VR.FD]:
                    cast_value = None
            except Exception:
                logging.error(f"Failed in casting {value_as_string} to VR of {vr_as_string}")
            cast_values.append(cast_value)
        return cast_values

    def _group_hex_editing_finished(self):
        group_hex_text = self.ui.line_edit_group_hex.text()
        if len(group_hex_text) == 0:
            return

        group_hex = int(group_hex_text, 16)

        element_hex_text = self.ui.line_edit_element_hex.text()
        if len(element_hex_text) == 0:
            return

        element_hex = int(element_hex_text, 16)

        private_creator = self.ui.combo_box_creator_list.currentText()
        if len(private_creator) == 0:
            return

        self._set_attribute_name_text_from_group_and_element(group_hex, element_hex, private_creator)

    def _set_attribute_name_text_from_group_and_element(self, group: int, element: int, creator: str):
        try:
            dict_entry_tuple = datadict.get_private_entry((group, element), creator)
            vr = dict_entry_tuple[0]
            vm = dict_entry_tuple[1]
            name = dict_entry_tuple[2]
            is_retired = dict_entry_tuple[3]
            # keyword = dict_entry_tuple[4]
        except KeyError:
            logging.warning(f"Not found in private dictionary: {group:04x},{element:04x} {creator}")
            return
        self.ui.line_edit_attribute_name.setText(name)
        element_value = None
        plain_text = self.ui.text_edit_element_value.toPlainText()
        if plain_text is not None and len(plain_text) > 0:
            value_list = self._convert_text_lines_to_vr_values(plain_text, vr)
            if len(value_list) == 0:
                element_value = None
            elif len(value_list) == 1:
                element_value = value_list[0]
            else:
                element_value = value_list

        # TODO: deal with multi-valued element by parsing text
        # TODO: deal with numeric valued element by converting text
        self.current_private_dataset = Dataset()
        self.current_private_block = self.current_private_dataset.private_block(group, creator, create=True)

        self.current_private_block.add_new(element, vr, element_value)
        self.current_byte_offset = element

        return

    def _element_hex_editing_finished(self):
        element_hex_text = self.ui.line_edit_element_hex.text()
        if len(element_hex_text) == 0:
            return

        element_hex = int(element_hex_text, 16)
        group_hex_text = self.ui.line_edit_group_hex.text()
        if len(group_hex_text) == 0:
            return

        group_hex = int(group_hex_text, 16)
        private_creator = self.ui.combo_box_creator_list.currentText()
        if len(private_creator) == 0:
            return

        self._set_attribute_name_text_from_group_and_element(group_hex, element_hex, private_creator)
