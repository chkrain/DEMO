#!/usr/bin/python3
from AnyQt.QtGui import QIcon
from AnyQt.QtWidgets import QWidget
from AnyQt.QtDesigner import QPyDesignerCustomWidgetPlugin

# Пример пользовательского плагина для Qt Designer

# try:
#     class __CustomPlugin(QPyDesignerCustomWidgetPlugin):

#         def __init__(self, parent=None):
#             super().__init__(parent)

#             self.initialized = False

#         def initialize(self, core):
#             if self.initialized:
#                 return

#             self.initialized = True

#         def isInitialized(self):
#             return self.initialized

#         def createWidget(self, parent):
#             return QWidget(parent) # Custom widget creation

#         def name(self):
#             return "CustomPluginEx" # Custom widget name

#         def group(self):
#             return "PYSCA"

#         def icon(self):
#             return QIcon()

#         def toolTip(self):
#             return ""

#         def whatsThis(self):
#             return ""

#         def isContainer(self):
#             return False

#         def includeFile(self):
#             return "gui.customplugin" # Custom widget include file
# except:
#     pass
