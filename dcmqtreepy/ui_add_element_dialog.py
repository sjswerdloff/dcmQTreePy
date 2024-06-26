# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'add_element_dialog.ui'
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
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTextEdit,
    QWidget,
)


class Ui_add_element_dialog(object):
    def setupUi(self, add_element_dialog):
        if not add_element_dialog.objectName():
            add_element_dialog.setObjectName("add_element_dialog")
        add_element_dialog.resize(349, 425)
        self.gridLayout_2 = QGridLayout(add_element_dialog)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.group_box_element_value = QGroupBox(add_element_dialog)
        self.group_box_element_value.setObjectName("group_box_element_value")
        self.text_edit_element_value = QTextEdit(self.group_box_element_value)
        self.text_edit_element_value.setObjectName("text_edit_element_value")
        self.text_edit_element_value.setGeometry(QRect(15, 33, 256, 192))

        self.gridLayout_2.addWidget(self.group_box_element_value, 1, 0, 1, 1)

        self.group_box_attribute = QGroupBox(add_element_dialog)
        self.group_box_attribute.setObjectName("group_box_attribute")
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

        self.gridLayout_2.addWidget(self.group_box_attribute, 0, 0, 1, 1)

        self.buttonBox = QDialogButtonBox(add_element_dialog)
        self.buttonBox.setObjectName("buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)

        self.gridLayout_2.addWidget(self.buttonBox, 2, 0, 1, 1)

        self.retranslateUi(add_element_dialog)
        self.buttonBox.accepted.connect(add_element_dialog.accept)
        self.buttonBox.rejected.connect(add_element_dialog.reject)

        QMetaObject.connectSlotsByName(add_element_dialog)

    # setupUi

    def retranslateUi(self, add_element_dialog):
        add_element_dialog.setWindowTitle(QCoreApplication.translate("add_element_dialog", "Dialog", None))
        self.group_box_element_value.setTitle(QCoreApplication.translate("add_element_dialog", "Value", None))
        self.group_box_attribute.setTitle(QCoreApplication.translate("add_element_dialog", "Attribute", None))
        self.label_attribute_group.setText(QCoreApplication.translate("add_element_dialog", "Group", None))
        self.label_attribute_name.setText(QCoreApplication.translate("add_element_dialog", "Name", None))
        self.label_attribute_element.setText(QCoreApplication.translate("add_element_dialog", "Element", None))

    # retranslateUi
