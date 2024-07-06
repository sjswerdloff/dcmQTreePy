# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainwindow.ui'
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
    QAction,
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
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        MainWindow.setAcceptDrops(True)
        self.actionFile = QAction(MainWindow)
        self.actionFile.setObjectName("actionFile")
        self.actionOpen = QAction(MainWindow)
        self.actionOpen.setObjectName("actionOpen")
        self.actionSave = QAction(MainWindow)
        self.actionSave.setObjectName("actionSave")
        self.actionSave_As = QAction(MainWindow)
        self.actionSave_As.setObjectName("actionSave_As")
        self.actionAdd_Element = QAction(MainWindow)
        self.actionAdd_Element.setObjectName("actionAdd_Element")
        self.actionAdd_Private_Element = QAction(MainWindow)
        self.actionAdd_Private_Element.setObjectName("actionAdd_Private_Element")
        self.central_widget = QWidget(MainWindow)
        self.central_widget.setObjectName("central_widget")
        self.formLayout_5 = QFormLayout(self.central_widget)
        self.formLayout_5.setObjectName("formLayout_5")
        self.groupBox = QGroupBox(self.central_widget)
        self.groupBox.setObjectName("groupBox")
        self.formLayout_2 = QFormLayout(self.groupBox)
        self.formLayout_2.setObjectName("formLayout_2")
        self.scrollArea = QScrollArea(self.groupBox)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 744, 213))
        self.formLayout = QFormLayout(self.scrollAreaWidgetContents)
        self.formLayout.setObjectName("formLayout")
        self.listWidget = QListWidget(self.scrollAreaWidgetContents)
        self.listWidget.setObjectName("listWidget")
        self.listWidget.setAcceptDrops(True)
        self.listWidget.setAutoFillBackground(True)
        self.listWidget.setSelectionRectVisible(True)

        self.formLayout.setWidget(0, QFormLayout.SpanningRole, self.listWidget)

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.formLayout_2.setWidget(0, QFormLayout.SpanningRole, self.scrollArea)

        self.formLayout_5.setWidget(0, QFormLayout.SpanningRole, self.groupBox)

        self.groupBox_2 = QGroupBox(self.central_widget)
        self.groupBox_2.setObjectName("groupBox_2")
        self.formLayout_3 = QFormLayout(self.groupBox_2)
        self.formLayout_3.setObjectName("formLayout_3")
        self.scrollArea_2 = QScrollArea(self.groupBox_2)
        self.scrollArea_2.setObjectName("scrollArea_2")
        self.scrollArea_2.setWidgetResizable(True)
        self.scrollAreaWidgetContents_2 = QWidget()
        self.scrollAreaWidgetContents_2.setObjectName("scrollAreaWidgetContents_2")
        self.scrollAreaWidgetContents_2.setGeometry(QRect(0, 0, 744, 210))
        self.formLayout_4 = QFormLayout(self.scrollAreaWidgetContents_2)
        self.formLayout_4.setObjectName("formLayout_4")
        self.treeWidget = QTreeWidget(self.scrollAreaWidgetContents_2)
        __qtreewidgetitem = QTreeWidgetItem()
        __qtreewidgetitem.setText(4, "5")
        __qtreewidgetitem.setText(3, "4")
        __qtreewidgetitem.setText(2, "Value")
        __qtreewidgetitem.setText(1, "Name")
        __qtreewidgetitem.setText(0, "Tag")
        self.treeWidget.setHeaderItem(__qtreewidgetitem)
        self.treeWidget.setObjectName("treeWidget")
        self.treeWidget.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.treeWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.treeWidget.setAlternatingRowColors(True)
        self.treeWidget.setIndentation(4)
        self.treeWidget.setColumnCount(5)

        self.formLayout_4.setWidget(0, QFormLayout.SpanningRole, self.treeWidget)

        self.scrollArea_2.setWidget(self.scrollAreaWidgetContents_2)

        self.formLayout_3.setWidget(0, QFormLayout.SpanningRole, self.scrollArea_2)

        self.formLayout_5.setWidget(1, QFormLayout.SpanningRole, self.groupBox_2)

        MainWindow.setCentralWidget(self.central_widget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 37))
        self.menuMain_Window = QMenu(self.menubar)
        self.menuMain_Window.setObjectName("menuMain_Window")
        self.menuEdit = QMenu(self.menubar)
        self.menuEdit.setObjectName("menuEdit")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuMain_Window.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menuMain_Window.addAction(self.actionOpen)
        self.menuMain_Window.addAction(self.actionSave)
        self.menuMain_Window.addAction(self.actionSave_As)
        self.menuEdit.addAction(self.actionAdd_Element)
        self.menuEdit.addAction(self.actionAdd_Private_Element)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", "DCMQTreePy", None))
        self.actionFile.setText(QCoreApplication.translate("MainWindow", "File", None))
        self.actionOpen.setText(QCoreApplication.translate("MainWindow", "Open", None))
        self.actionSave.setText(QCoreApplication.translate("MainWindow", "Save", None))
        self.actionSave_As.setText(QCoreApplication.translate("MainWindow", "Save As...", None))
        self.actionAdd_Element.setText(QCoreApplication.translate("MainWindow", "Add Element", None))
        self.actionAdd_Private_Element.setText(QCoreApplication.translate("MainWindow", "Add Private Element", None))
        self.groupBox.setTitle(QCoreApplication.translate("MainWindow", "Files", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("MainWindow", "DICOM Elements", None))
        self.menuMain_Window.setTitle(QCoreApplication.translate("MainWindow", "File", None))
        self.menuEdit.setTitle(QCoreApplication.translate("MainWindow", "Edit", None))

    # retranslateUi
