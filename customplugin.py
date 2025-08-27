#!/usr/bin/python3
from AnyQt.QtGui import QIcon, QPixmap
from AnyQt.QtCore import pyqtProperty, pyqtSignal, Qt, QDir
from AnyQt.QtWidgets import QWidget, QLabel, QPushButton, QApplication
from AnyQt.QtDesigner import QPyDesignerCustomWidgetPlugin
from pysca.helpers import custom_widget_plugin, custom_widget
import os

class CtlGen(custom_widget('ui/ctlgen.ui')):    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        
        # Инициализация состояний
        self._manual_mode = False
        self._is_working = False
        self._start_active = False
        
        # Настройка путей к изображениям
        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        self._img_dir = os.path.join(self._base_dir, "img")
        
        # Настройка начального вида
        self.update_ui()
        
        # Подключение сигналов кнопок
        self.button_start.clicked.connect(self.on_start_clicked)
        self.button_stop.clicked.connect(self.on_stop_clicked)
    
    def title(self) -> str:
        return self.name.text()
    
    def setTitle(self, title: str):
        self.name.setText(title)
    
    def isManualMode(self) -> bool:
        return self._manual_mode
    
    def setManualMode(self, manual: bool):
        self._manual_mode = manual
        self.update_manual_icon()
        self.update_buttons_state()
    
    def isWorking(self) -> bool:
        return self._is_working
    
    def setWorking(self, working: bool):
        self._is_working = working
        self.update_work_icon()
        self.update_buttons_state()
    
    def isStartActive(self) -> bool:
        return self._start_active
    
    def setStartActive(self, active: bool):
        self._start_active = active
        self.update_buttons_state()
    
    def update_ui(self):
        self.update_manual_icon()
        self.update_work_icon()
        self.update_buttons_state()
    
    def update_manual_icon(self):
        icon_name = "РУКА АКТИВ.png" if self._manual_mode else "РУКА СЕР.png"
        icon_path = os.path.join(self._img_dir, icon_name)
        if os.path.exists(icon_path):
            self.manual.setPixmap(QPixmap(icon_path))
        else:
            print(f"Warning: Image not found - {icon_path}")
    
    def update_work_icon(self):
        icon_name = "ПРОЦ АКТИВ.png" if self._is_working else "ПРОЦ СЕР111.png"
        icon_path = os.path.join(self._img_dir, icon_name)
        if os.path.exists(icon_path):
            self.work.setPixmap(QPixmap(icon_path))
        else:
            print(f"Warning: Image not found - {icon_path}")
    
    def update_buttons_state(self):
        # Обновление иконки ручного режима
        self.update_manual_icon()
        
        # Обновление иконки работы (только если не в ручном режиме)
        if not self._manual_mode:
            self.update_work_icon()
        else:
            # В ручном режиме всегда серая иконка работы
            icon_path = os.path.join(self._img_dir, "ПРОЦ СЕР111.png")
            if os.path.exists(icon_path):
                self.work.setPixmap(QPixmap(icon_path))
        
        # Состояние кнопок
        if self._manual_mode:
            # Ручной режим - обе кнопки недоступны
            self.button_start.setEnabled(False)
            self.button_stop.setEnabled(False)
            self.button_start.setStyleSheet("background-color: #9E9E9E; color: white;")
            self.button_stop.setStyleSheet("background-color: #9E9E9E; color: white;")
        else:
            # Автоматический режим
            if self._is_working:
                # Работает - старт недоступен, стоп доступен
                self.button_start.setEnabled(False)
                self.button_stop.setEnabled(True)
                self.button_start.setStyleSheet("background-color: #9E9E9E; color: white;")
                self.button_stop.setStyleSheet("background-color: #F44336; color: white;")
            else:
                # Не работает - старт доступен, стоп недоступен
                self.button_start.setEnabled(True)
                self.button_stop.setEnabled(False)
                self.button_start.setStyleSheet("background-color: #4CAF50; color: white;")
                self.button_stop.setStyleSheet("background-color: #9E9E9E; color: white;")

    def on_start_clicked(self):
        if not self._manual_mode and not self._is_working:
            self._is_working = True
            self.setProperty('isWorking', True)
            self.update_ui()

    def on_stop_clicked(self):
        if not self._manual_mode and self._is_working:
            self._is_working = False
            self.setProperty('isWorking', False)
            self.update_ui()
    
    def on_start_clicked(self):
        if not self._manual_mode:  # Только если не в ручном режиме
            self._start_active = not self._start_active
            self._is_working = self._start_active  # Включаем режим работы сразу при старте
            self.setProperty('start', self._start_active)
            self.setProperty('isWorking', self._is_working)
            self.update_ui()
    
    def on_stop_clicked(self):
        if not self._manual_mode and self._start_active:
            self._is_working = False  # Выключаем режим работы
            self.setProperty('isWorking', False)
            self.update_ui()

    # Свойства для Qt Designer
    title = pyqtProperty(str, fget=title, fset=setTitle)
    manualMode = pyqtProperty(bool, fget=isManualMode, fset=setManualMode)
    working = pyqtProperty(bool, fget=isWorking, fset=setWorking)
    startActive = pyqtProperty(bool, fget=isStartActive, fset=setStartActive)

__ctlgenplugin = custom_widget_plugin(CtlGen, 'CtlGen', False, 'DEMO', 'customplugin')