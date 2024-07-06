# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'add_private_element_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QDate,
    QDateTime,
    QLocale,
    QMetaObject,
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTime,
    QUrl,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QFontDatabase,
    QGradient,
    QIcon,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTextEdit,
    QWidget,
)


class Ui_add_private_element_dialog(object):
    def setupUi(self, add_private_element_dialog):
        if not add_private_element_dialog.objectName():
            add_private_element_dialog.setObjectName("add_private_element_dialog")
        add_private_element_dialog.resize(349, 503)
        self.group_box_element_value = QGroupBox(add_private_element_dialog)
        self.group_box_element_value.setObjectName("group_box_element_value")
        self.group_box_element_value.setGeometry(QRect(10, 260, 325, 171))
        self.text_edit_element_value = QTextEdit(self.group_box_element_value)
        self.text_edit_element_value.setObjectName("text_edit_element_value")
        self.text_edit_element_value.setGeometry(QRect(15, 33, 256, 131))
        self.group_box_attribute = QGroupBox(add_private_element_dialog)
        self.group_box_attribute.setObjectName("group_box_attribute")
        self.group_box_attribute.setGeometry(QRect(10, 100, 325, 151))
        self.line_edit_group_hex = QLineEdit(self.group_box_attribute)
        self.line_edit_group_hex.setObjectName("line_edit_group_hex")
        self.line_edit_group_hex.setGeometry(QRect(15, 33, 125, 21))
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.line_edit_group_hex.sizePolicy().hasHeightForWidth())
        self.line_edit_group_hex.setSizePolicy(sizePolicy)
        self.label_attribute_group = QLabel(self.group_box_attribute)
        self.label_attribute_group.setObjectName("label_attribute_group")
        self.label_attribute_group.setGeometry(QRect(15, 64, 37, 16))
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(1)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label_attribute_group.sizePolicy().hasHeightForWidth())
        self.label_attribute_group.setSizePolicy(sizePolicy1)
        self.line_edit_attribute_name = QLineEdit(self.group_box_attribute)
        self.line_edit_attribute_name.setObjectName("line_edit_attribute_name")
        self.line_edit_attribute_name.setGeometry(QRect(77, 90, 211, 21))
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.line_edit_attribute_name.sizePolicy().hasHeightForWidth())
        self.line_edit_attribute_name.setSizePolicy(sizePolicy2)
        self.line_edit_attribute_name.setReadOnly(True)
        self.label_attribute_name = QLabel(self.group_box_attribute)
        self.label_attribute_name.setObjectName("label_attribute_name")
        self.label_attribute_name.setGeometry(QRect(15, 90, 35, 16))
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.label_attribute_name.sizePolicy().hasHeightForWidth())
        self.label_attribute_name.setSizePolicy(sizePolicy3)
        self.label_attribute_element = QLabel(self.group_box_attribute)
        self.label_attribute_element.setObjectName("label_attribute_element")
        self.label_attribute_element.setGeometry(QRect(173, 64, 49, 16))
        self.line_edit_element_hex = QLineEdit(self.group_box_attribute)
        self.line_edit_element_hex.setObjectName("line_edit_element_hex")
        self.line_edit_element_hex.setGeometry(QRect(173, 33, 125, 21))
        sizePolicy.setHeightForWidth(self.line_edit_element_hex.sizePolicy().hasHeightForWidth())
        self.line_edit_element_hex.setSizePolicy(sizePolicy)
        self.buttonBox = QDialogButtonBox(add_private_element_dialog)
        self.buttonBox.setObjectName("buttonBox")
        self.buttonBox.setGeometry(QRect(180, 460, 152, 32))
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.group_private_block = QGroupBox(add_private_element_dialog)
        self.group_private_block.setObjectName("group_private_block")
        self.group_private_block.setGeometry(QRect(20, 0, 291, 70))
        self.label = QLabel(self.group_private_block)
        self.label.setObjectName("label")
        self.label.setGeometry(QRect(10, 30, 51, 20))
        self.combo_box_creator_list = QComboBox(self.group_private_block)
        self.combo_box_creator_list.setObjectName("combo_box_creator_list")
        self.combo_box_creator_list.setGeometry(QRect(90, 30, 181, 20))
        self.combo_box_creator_list.setEditable(False)

        self.retranslateUi(add_private_element_dialog)
        self.buttonBox.accepted.connect(add_private_element_dialog.accept)
        self.buttonBox.rejected.connect(add_private_element_dialog.reject)

        QMetaObject.connectSlotsByName(add_private_element_dialog)

    # setupUi

    def retranslateUi(self, add_private_element_dialog):
        add_private_element_dialog.setWindowTitle(QCoreApplication.translate("add_private_element_dialog", "Dialog", None))
        self.group_box_element_value.setTitle(QCoreApplication.translate("add_private_element_dialog", "Value", None))
        self.group_box_attribute.setTitle(QCoreApplication.translate("add_private_element_dialog", "Attribute", None))
        self.label_attribute_group.setText(QCoreApplication.translate("add_private_element_dialog", "Group", None))
        self.label_attribute_name.setText(QCoreApplication.translate("add_private_element_dialog", "Name", None))
        self.label_attribute_element.setText(QCoreApplication.translate("add_private_element_dialog", "Byte", None))
        self.group_private_block.setTitle(QCoreApplication.translate("add_private_element_dialog", "Private", None))
        self.label.setText(QCoreApplication.translate("add_private_element_dialog", "Creator", None))

    # retranslateUi
