from pyplc.platform import plc
from pyplc.utils.latch import RS
from pyplc.utils.misc import TON
from pyplc.sfc import SFC, POU
from umodbus.tcp import TCP as ModbusTCPMaster
import time

from pyplc.utils.bindable import Property

class Mechanism(SFC):
    """Класс для механизмов (дробилки, грохоты, шнеки)"""
    
    # Определяем входы/выходы как свойства POU
    start_signal = POU.input(False,hidden=True)
    manual_signal = POU.input(False,hidden=True)
    stop_signal = POU.input(False,hidden=True)
    output_signal = POU.output(False,hidden=True)

    rstart = POU.var(False)
    rstop = POU.var(False)
    
    def __init__(self, start_signal:bool, manual_signal=None, stop_signal=None, 
                 output_signal=None, name=None, id: str = None, parent: POU = None):
        super().__init__(id=id, parent=parent)
        self.name = name or id or "Mechanism"
        
        # Инициализация сигналов
        self.start_signal = start_signal
        self.manual_signal = manual_signal
        self.stop_signal = stop_signal
        self.output_signal = output_signal
        
        self.rs = RS( )
        # self.subtasks = ( self.man_ctl, )
        # self.ton = TON(pt=startup_time)
        # self.ready = False
        # self.running = False
    
    def auto_ctl(self, x: bool):
        if not self.manual: return
        self.q = x
        
    def main(self):
        # Базовая логика для механизмов
        if not self.manual_signal:
            set_condition =  self.rstart
            reset_condition =  self.rstop
        elif self.manual_signal:
            set_condition =  self.start_signal
            reset_condition = not self.stop_signal
        
        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q

        # Таймер для времени запуска
        # self.ton(clk=self.rs.q)
        # self.ready = self.ton.et >= self.startup_time
        # self.running = self.rs.q
            
        yield

class Conveyor(SFC):
    """Класс для конвейеров с частотным управлением"""
    
    # Определяем входы/выходы как свойства POU
    start_signal = POU.input(False)
    manual_signal = POU.input(False)
    stop_signal = POU.input(False)
    output_signal = POU.output(False)
    rope_switch_signal = POU.input(False)
    belt_break_signal = POU.input(False)

    rstart = POU.var(False)
    rstop = POU.var(False)
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, 
                 output_signal=None, rope_switch_signal=None, belt_break_signal=None, 
                 name=None, slave_addr=1, 
                 id: str = None, parent: POU = None):
        
        super().__init__(id=id, parent=parent)
        
        self.name = name or id or "Conveyor"
        self.slave_addr = slave_addr
        
        # Инициализация сигналов

        self.start_signal = start_signal
        self.manual_signal = manual_signal
        self.stop_signal = stop_signal
        self.output_signal = output_signal
        self.rope_switch_signal = rope_switch_signal
        self.belt_break_signal = belt_break_signal
        
        self.rs = RS()

        self.ready = False
        self.running = False
        
        # Для обнаружения заклинивания ленты
        self.last_belt_state = None
        self.belt_stuck_time = 0
        
    def main(self):

        while True:
            if self.manual_signal:
                set_condition = (self.start_signal)
                
                reset_conditions = [not self.stop_signal]
                
                # Тросовый выключатель
                reset_conditions.append(self.rope_switch_signal)
                
                # Обрыв ленты 
                break_detected = self._check_belt_stuck()
                reset_conditions.append(break_detected)
                
                reset_condition = any(reset_conditions)
            elif not self.manual_signal:
                set_condition = (self.rstart)
                break_detected = self._check_belt_stuck()
                reset_condition = (self.rstop or self.rope_switch_signal or break_detected)
            
            self.rs(set=set_condition, reset=reset_condition)
            self.output_signal = self.rs.q
            
            # Управление частотником
            self._frequency_control()
            
            yield
    
    def _frequency_control(self):
        """Управление частотным преобразователем"""
        try:
            if self.rs.q:
                print(f"{self.name}: Запуск ЧП, адрес {self.slave_addr}")
                # Включение и установка скорости
                host.write_single_register(
                    slave_addr=self.slave_addr, 
                    register_address=2, 
                    register_value=1000
                )
                host.write_single_register(
                    slave_addr=self.slave_addr, 
                    register_address=1, 
                    register_value=2178  # Команда запуска
                )
            else:
                # Выключение
                host.write_single_register(
                    slave_addr=self.slave_addr, 
                    register_address=1, 
                    register_value=2177  # Команда остановки
                )
        except Exception as e:
            print(f'{self.name}: Ошибка Modbus - {e}')
        
    def _check_belt_stuck(self):
        if self.belt_break_signal is None:
            return False
            
        current_state = self.belt_break_signal
        
        if not self.rs.q:
            self.belt_stuck_time = 0
            self.last_belt_state = None
            return False
        
        if self.last_belt_state is None:
            self.last_belt_state = current_state
            self.belt_stuck_time = 0
            return False
        
        if current_state != self.last_belt_state:
            self.last_belt_state = current_state
            self.belt_stuck_time = 0
            return False
        else:
            self.belt_stuck_time += 100
        
        result = (self.belt_stuck_time >= 7000) and self.rs.q
        return result

# Глобальная инициализация Modbus
slave_tcp_port = 502
slave_ip = '192.168.8.15'
host = ModbusTCPMaster(
    slave_ip=slave_ip,
    slave_port=slave_tcp_port,
    timeout=0.1
)

# Создаем экземпляры механизмов и конвейеров
drob_m4 = Mechanism(
    start_signal=plc.DI_STATION4_START,
    manual_signal=plc.DI_STATION4_MANUAL,
    stop_signal=plc.DI_STATION4_STOP,
    output_signal=plc.DO_ROLLERCRUSHER_TURNON,
    name="Дробилка M4"
)

conv_m14 = Conveyor(
    start_signal=plc.DI_STATION12_START,
    manual_signal=plc.DI_STATION12_MANUAL,
    stop_signal=plc.DI_STATION12_STOP,
    output_signal=plc.DO_CONVEYOR6508000_DRUM_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6508000_ROPESWITCH2_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6508000_BELTBREAK2_TRIPPED,
    name="Конвейер M14",
    slave_addr=5
)

plc.run(instances=[drob_m4, conv_m14], ctx=globals())