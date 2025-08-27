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

class Feeder(Conveyor):
    
    panel_start = POU.input(False)  
    panel_stop = POU.input(False) 
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, 
                 output_signal=None, rope_switch_signal=None, belt_break_signal=None, 
                 panel_start=None, panel_stop=None,  # Новые параметры пульта
                 name=None, slave_addr=1, 
                 id: str = None, parent: POU = None):
        
        super().__init__(
            start_signal=start_signal,
            manual_signal=manual_signal,
            stop_signal=stop_signal,
            output_signal=output_signal,
            rope_switch_signal=rope_switch_signal,
            belt_break_signal=belt_break_signal,
            name=name,
            slave_addr=slave_addr,
            id=id,
            parent=parent
        )
        
        self.name = name or id or "Feeder"
        self.panel_start = panel_start
        self.panel_stop = panel_stop
    
    def main(self):
        while True:
            if self.manual_signal:
                set_condition = (self.start_signal or self.panel_start)
                
                reset_conditions = [
                    not self.stop_signal,
                    self.panel_stop 
                ]
                reset_conditions.append(self.rope_switch_signal)
                
                break_detected = self._check_belt_stuck()
                reset_conditions.append(break_detected)
                
                reset_condition = any(reset_conditions)
                
            elif not self.manual_signal:
                set_condition = (self.rstart or self.panel_start)
                break_detected = self._check_belt_stuck()
                reset_condition = (self.rstop or self.rope_switch_signal or break_detected or self.panel_stop)
            
            self.rs(set=set_condition, reset=reset_condition)
            self.output_signal = self.rs.q
            
            self._frequency_control()
            
            # Логирование для отладки
            print(f'{self.name}: RemoteStart={self.remote_start}, RemoteStop={self.remote_stop}, Output={self.output_signal}')
            
            yield

# Глобальная инициализация Modbus
slave_tcp_port = 502
slave_ip = '192.168.8.15'
host = ModbusTCPMaster(
    slave_ip=slave_ip,
    slave_port=slave_tcp_port,
    timeout=0.1
)

# ленточный питатель

feeder_m1 = Feeder(
    start_signal=plc.DI_STATION1_START,
    manual_signal=plc.DI_STATION1_MANUAL,
    stop_signal=plc.DI_STATION1_STOP,
    output_signal=plc.DO_BELTFEEDER_TURNON,
    rope_switch_signal=plc.DI_BELTFEEDER_ROPESWITCH_TRIPPED ,
    belt_break_signal=plc.DI_BELTFEEDER_BELTBREAK_TRIPPED,
    panel_start=plc.DI_PANEL1_START,      
    panel_stop=plc.DI_PANEL1_STOP,      
    name="Питатель M1",
    slave_addr=1
)

# экземпляры механизмов 

izm_m2 = Mechanism(
    start_signal=plc.DI_STATION2_START,
    manual_signal=plc.DI_STATION2_MANUAL,
    stop_signal=plc.DI_STATION2_STOP,
    output_signal=plc.DO_ROTARYCRUSHER_TURNON,
    name="Измельчитель M2"
)

drob_m4 = Mechanism(
    start_signal=plc.DI_STATION4_START,
    manual_signal=plc.DI_STATION4_MANUAL,
    stop_signal=plc.DI_STATION4_STOP,
    output_signal=plc.DO_ROLLERCRUSHER_TURNON,
    name="Дробилка M4"
)

groh_m6 = Mechanism(
    start_signal=plc.DI_STATION6_START,
    manual_signal=plc.DI_STATION6_MANUAL,
    stop_signal=plc.DI_STATION6_STOP,
    output_signal=plc.DO_DOUBLEMESHSCREEN_TURNON,
    name="Грохот M6"
)

drob_m15 = Mechanism(
    start_signal=plc.DI_STATION13_START,
    manual_signal=plc.DI_STATION13_MANUAL,
    stop_signal=plc.DI_STATION13_STOP,
    output_signal=plc.DO_ROLLERCRUSHER2_TURNON,
    name='Дробилка M15'
)

groh_m17 = Mechanism(
    start_signal=plc.DI_STATION15_START,
    manual_signal=plc.DI_STATION15_MANUAL,
    stop_signal=plc.DI_STATION15_STOP,
    output_signal=plc.DO_DOUBLEMESHSCREEN2_TURNON,
    name='Грохот M17'
)

# экземпляры конвейеров

conv_m3 = Conveyor(
    start_signal=plc.DI_STATION3_START,
    manual_signal=plc.DI_STATION3_MANUAL,
    stop_signal=plc.DI_STATION3_STOP,
    output_signal=plc.DO_CONVEYOR6506000_CRUSHER_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6508000_ROPESWITCH_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6508000_BELTBREAK_TRIPPED,
    name='Конвейер на дробилку M4',
    slave_addr=2
)

conv_m5 = Conveyor(
    start_signal=plc.DI_STATION5_START,
    manual_signal=plc.DI_STATION5_MANUAL,
    stop_signal=plc.DI_STATION5_STOP,
    output_signal=plc.DO_CONVEYOR6506000_BOLT_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6506000_ROPESWITCH_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6506000_BELTBREAK_TRIPPED,
    name='Конвейер на грохот M6',
    slave_addr=9
)

conv_m7 = Conveyor(
    start_signal=plc.DI_STATION7_START,
    manual_signal=plc.DI_STATION7_MANUAL,
    stop_signal=plc.DI_STATION7_STOP,
    output_signal=plc.DO_CONVEYOR6506000_HOPPER_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6506000_ROPESWITCH2_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6506000_BELTBREAK2_TRIPPED,
    name='Конвейер на бункер накопительный',
    slave_addr=10
)

conv_m8 = Conveyor(
    start_signal=plc.DI_STATION8_START,
    manual_signal=plc.DI_STATION8_MANUAL,
    stop_signal=plc.DI_STATION8_STOP,
    output_signal=plc.DO_CONVEYOR6506000_PACKING_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6506000_ROPESWITCH3_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6506000_BELTBREAK3_TRIPPED,
    name='Конвейер на станцию фасовки',
    slave_addr=11
)

conv_m10 = Conveyor(
    start_signal=plc.DI_STATION9_START,
    manual_signal=plc.DI_STATION9_MANUAL,
    stop_signal=plc.DI_STATION9_STOP,
    output_signal=plc.DO_CONVEYOR6501000_DRUM_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR65010000_ROPESWITCH_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR65010000_BELTBREAK_TRIPPED,
    name='Конвейер в сушильный барабан',
    slave_addr=3
)

conv_m14 = Conveyor(
    start_signal=plc.DI_STATION12_START,
    manual_signal=plc.DI_STATION12_MANUAL,
    stop_signal=plc.DI_STATION12_STOP,
    output_signal=plc.DO_CONVEYOR6508000_DRUM_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6508000_ROPESWITCH2_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6508000_BELTBREAK2_TRIPPED,
    name="Конвейер M14 после сушильного барабана",
    slave_addr=5
)

conv_m16 = Conveyor(
    start_signal=plc.DI_STATION14_START,
    manual_signal=plc.DI_STATION14_MANUAL,
    stop_signal=plc.DI_STATION14_STOP,
    output_signal=plc.DO_CONVEYOR6508000_SCREEN_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6508000_ROPESWITCH3_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6508000_BELTBREAK3_TRIPPED,
    name="Конвейер M16 на грохот 2",
    slave_addr=6
)

conv_m18 = Conveyor(
    start_signal=plc.DI_STATION16_START,
    manual_signal=plc.DI_STATION16_MANUAL,
    stop_signal=plc.DI_STATION16_STOP,
    output_signal=plc.DO_CONVEYOR6506000_BIN38_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6506000_ROPESWITCH4_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6506000_BELTBREAK4_TRIPPED,
    name="Конвейер M18 на бункер 3-8мм",
    slave_addr=12
)

conv_m19 = Conveyor(
    start_signal=plc.DI_STATION17_START,
    manual_signal=plc.DI_STATION17_MANUAL,
    stop_signal=plc.DI_STATION17_STOP,
    output_signal=plc.DO_CONVEYOR6506000_BIN02_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6506000_ROPESWITCH5_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6506000_BELTBREAK5_TRIPPED,
    name="Конвейер M19 на бункер 0-2мм",
    slave_addr=13
)

conv_m20 = Conveyor(
    start_signal=plc.DI_STATION18_START,
    manual_signal=plc.DI_STATION18_MANUAL,
    stop_signal=plc.DI_STATION18_STOP,
    output_signal=plc.DO_CONVEYOR6501000_PACKING_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR65010000_ROPESWITCH2_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR65010000_BELTBREAK2_TRIPPED,
    name="Конвейер M20 на станцию фасовки",
    slave_addr=7
)


plc.run(instances=[drob_m4, groh_m6, conv_m14, groh_m17, drob_m15], ctx=globals())