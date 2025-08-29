from pyplc.platform import plc
from pyplc.utils.latch import RS
from pyplc.utils.misc import TON
from pyplc.sfc import SFC, POU
from umodbus.tcp import TCP as ModbusTCPMaster
from pyplc.utils.trig import RTRIG, FTRIG
import time

class Mechanism(SFC):
    """Класс для механизмов (дробилки, грохоты, шнеки)"""
    
    # Определяем входы/выходы как свойства POU
    start_signal = POU.input(False,hidden=True)
    manual_signal = POU.input(False,hidden=True)
    stop_signal = POU.input(False,hidden=True)
    output_signal = POU.output(False,hidden=True)

    emergency_stop = POU.input(False, hidden=True)

    rstart = POU.var(False)
    rstop = POU.var(False)
    
    def __init__(self, start_signal:bool, manual_signal=None, stop_signal=None, 
                 output_signal=None, name=None, id: str = None, parent: POU = None, emergency_stop=None):
        super().__init__(id=id, parent=parent)
        self.name = name or id or "Mechanism"
        
        # Инициализация сигналов
        self.start_signal = start_signal
        self.manual_signal = manual_signal
        self.stop_signal = stop_signal
        self.output_signal = output_signal
        self.emergency_stop = emergency_stop

        self.rs = RS( )
        # self.subtasks = ( self.man_ctl, )
        # self.ton = TON(pt=startup_time)
        # self.ready = False
        # self.running = False

    
    # def auto_ctl(self, x: bool):
    #     if not self.manual: return
    #     self.q = x
        
    def main(self):
        # Базовая логика для механизмов
        if not self.manual_signal:
            set_condition = self.rstart
            reset_condition = self.rstop or self.emergency_stop
            # print("main self if vеханизм", set_condition, reset_condition)
        else:
            set_condition =  self.start_signal 
            reset_condition = not self.stop_signal
            # print("main self else vеханизм", set_condition, reset_condition)

        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q
        

        yield


class Conveyor(SFC):
    """Класс для конвейеров с частотным управлением"""
    
    start_signal = POU.input(False)
    manual_signal = POU.input(None)
    stop_signal = POU.input(False)
    output_signal = POU.output(False)
    rope_switch_signal = POU.input(False)
    belt_break_signal = POU.input(False)

    emergency_stop = POU.input(False, hidden=True)

    rstart = POU.var(False)
    rstop = POU.var(False)
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, 
                 output_signal=None, rope_switch_signal=None, belt_break_signal=None, 
                 name=None, slave_addr=1, emergency_stop=None,
                 id: str = None, parent: POU = None):
        
        super().__init__(id=id, parent=parent)
        
        self.name = name or id or "Conveyor"
        self.slave_addr = slave_addr
        
        self.start_signal = start_signal
        self.manual_signal = manual_signal
        self.stop_signal = stop_signal
        self.output_signal = output_signal
        self.rope_switch_signal = rope_switch_signal
        self.belt_break_signal = belt_break_signal
        self.emergency_stop = emergency_stop
        
        self.rs = RS()
        self.ready = False
        self.running = False
        self.last_belt_state = None
        self.belt_stuck_time = 0
        self.last_modbus_call = 0
        
    def main(self):
        print(self.manual_signal)
        if self.manual_signal:
            set_condition = (self.start_signal)
                
            reset_conditions = [not self.stop_signal]
            reset_conditions.append(self.rope_switch_signal)
                
            break_detected = self._check_belt_stuck()
            reset_conditions.append(break_detected)
            reset_conditions.append(self.emergency_stop)
                
            reset_condition = any(reset_conditions)
            # print("main self if konveer", self.manual_signal)
        else:
            set_condition = (self.rstart)
            break_detected = self._check_belt_stuck()
            reset_condition = (self.rstop or self.rope_switch_signal or break_detected)
            # print("main self else konveer", self.manual_signal)
            
        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q
            
        self._frequency_control()
            
        yield
    
    def _frequency_control(self):
        if self.rs.q:
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=2, 
                register_value=200
            )
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=1, 
                register_value=2178  
            )
            # print("otpravka na chastotnik pusk", self.rs.q)
            
        else:
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=1, 
                register_value=2177 
            )
            # print("otpravka na chastotnik stop", self.rs.q)
        
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
        
        result = (self.belt_stuck_time >= 15000) and self.rs.q
        return result

class Feeder(SFC):
    """Класс для ленточного питателя с частотным управлением"""
    
    start_signal = POU.input(False)
    manual_signal = POU.input(None)
    stop_signal = POU.input(False)
    panel_start = POU.input(False)
    panel_stop = POU.input(False)
    output_signal = POU.output(False)
    rope_switch_signal = POU.input(False)
    belt_break_signal = POU.input(False)

    emergency_stop = POU.var(False)

    speed_value = POU.var(1)

    rstart = POU.var(False)
    rstop = POU.var(False)
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, panel_start=None, panel_stop=None,
                 output_signal=None, rope_switch_signal=None, belt_break_signal=None, 
                 name=None, slave_addr=1, emergency_stop=None, speed_value=1,
                 id: str = None, parent: POU = None):
        
        super().__init__(id=id, parent=parent)
        
        self.name = name or id or "Conveyor"
        self.slave_addr = slave_addr
        
        # Инициализация сигналов

        self.start_signal = start_signal
        self.manual_signal = manual_signal
        self.stop_signal = stop_signal
        self.panel_start = panel_start
        self.panel_stop = panel_stop
        self.output_signal = output_signal
        self.rope_switch_signal = rope_switch_signal
        self.belt_break_signal = belt_break_signal
        self.emergency_stop = emergency_stop
        self.speed_value = int(speed_value) * 10
        
        self.rs = RS()

        self.ready = False
        self.running = False
        self.last_belt_state = None
        self.belt_stuck_time = 0
        
    def main(self):
        if self.manual_signal:
            set_condition = (self.start_signal or self.panel_start)
            
            reset_conditions = [not self.stop_signal, not self.panel_stop, self.emergency_stop]
                
            reset_conditions.append(self.rope_switch_signal)

            reset_conditions.append(self.emergency_stop)
                
            break_detected = self._check_belt_stuck()
            reset_conditions.append(break_detected)
                
            reset_condition = any(reset_conditions)
        else:
            set_condition = (self.rstart or self.panel_start)
            break_detected = self._check_belt_stuck()
            reset_condition = (self.rstop or self.rope_switch_signal or break_detected or not self.panel_stop)
            
        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q
            
        self._frequency_control()
            
        yield
    
    def _frequency_control(self):
        if self.rs.q:
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=2, 
                register_value=200
            )
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=1, 
                register_value=2178  
            )
        else:
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=1, 
                register_value=2177 
            )
        
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


class Auger(SFC):
    start_signal = POU.input(False)
    manual_signal = POU.input(False)
    stop_signal = POU.input(False)
    output_signal = POU.output(False)

    emergency_stop = POU.input(False, hidden=True)

    rstart = POU.var(False)
    rstop = POU.var(False)
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, 
                 output_signal=None, name=None, slave_addr=1, emergency_stop=None,
                 id: str = None, parent: POU = None):
        
        super().__init__(id=id, parent=parent)
        
        self.name = name or id or "Auger"
        self.slave_addr = slave_addr
        
        self.start_signal = start_signal
        self.manual_signal = manual_signal
        self.stop_signal = stop_signal
        self.output_signal = output_signal
        self.emergency_stop = emergency_stop
        
        self.rs = RS()
        self.ready = False
        self.running = False

        
    def main(self):
        if self.manual_signal:
            set_condition = self.start_signal
            reset_condition = not self.stop_signal or self.emergency_stop
        else:
            set_condition = self.rstart
            reset_condition = self.rstop
            
        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q
            
        self._frequency_control()
            
        yield
    
    def _frequency_control(self):
        if self.rs.q:
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=2, 
                register_value=200
            )
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=1, 
                register_value=2178
            )
        else:
            # Выключение
            host.write_single_register(
                slave_addr=self.slave_addr, 
                register_address=1, 
                register_value=2177 
            )

class Drum(SFC):
    start_signal = POU.input(False)
    stop_signal = POU.input(False)
    output_signal = POU.output(False)

    # emergency_stop = POU.input(False, hidden=True)

    rstart = POU.var(False)
    rstop = POU.var(False)
    
    def __init__(self, start_signal=None, stop_signal=None, 
                 output_signal=None, name=None, emergency_stop=None,
                 id: str = None, parent: POU = None):
        
        super().__init__(id=id, parent=parent)
        
        self.name = name or id or "Drum"
        
        # Инициализация сигналов
        self.start_signal = start_signal
        self.stop_signal = stop_signal
        self.output_signal = output_signal
        self.emergency_stop = emergency_stop

        
        self.rs = RS()

        
    def main(self):
        set_condition = self.start_signal or self.rstart
        reset_condition = not self.stop_signal or self.rstop 
            
        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q
            
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
    slave_addr=1,
    speed_value=100
)

# экземпляры механизмов 

izm_m2 = Mechanism(
    start_signal=plc.DI_STATION2_START,
    manual_signal=plc.DI_STATION2_MANUAL,
    stop_signal=plc.DI_STATION2_STOP,
    output_signal=plc.DO_ROTARYCRUSHER_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Измельчитель M2"
)

drob_m4 = Mechanism(
    start_signal=plc.DI_STATION4_START,
    manual_signal=plc.DI_STATION4_MANUAL,
    stop_signal=plc.DI_STATION4_STOP,
    output_signal=plc.DO_ROLLERCRUSHER_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Дробилка M4"
)

groh_m6 = Mechanism(
    start_signal=plc.DI_STATION6_START,
    manual_signal=plc.DI_STATION6_MANUAL,
    stop_signal=plc.DI_STATION6_STOP,
    output_signal=plc.DO_DOUBLEMESHSCREEN_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Грохот M6"
)

drob_m15 = Mechanism(
    start_signal=plc.DI_STATION13_START,
    manual_signal=plc.DI_STATION13_MANUAL,
    stop_signal=plc.DI_STATION13_STOP,
    output_signal=plc.DO_ROLLERCRUSHER2_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name='Дробилка M15'
)

groh_m17 = Mechanism(
    start_signal=plc.DI_STATION15_START,
    manual_signal=plc.DI_STATION15_MANUAL,
    stop_signal=plc.DI_STATION15_STOP,
    output_signal=plc.DO_DOUBLEMESHSCREEN2_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name='Конвейер на дробилку M4',
    slave_addr=2
)

print(f"MANUAL M3 {plc.DI_STATION3_MANUAL}")

conv_m5 = Conveyor(
    start_signal=plc.DI_STATION5_START,
    manual_signal=plc.DI_STATION5_MANUAL,
    stop_signal=plc.DI_STATION5_STOP,
    output_signal=plc.DO_CONVEYOR6506000_BOLT_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6506000_ROPESWITCH_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6506000_BELTBREAK_TRIPPED,
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
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
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Конвейер M20 на станцию фасовки",
    slave_addr=7
)

# шнеки

auger_m13 = Mechanism(
    start_signal=plc.DI_STATION11_START,
    manual_signal=plc.DI_STATION11_MANUAL,
    stop_signal=plc.DI_STATION11_STOP,
    output_signal=plc.DO_SLUDGEAUGER_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Шнек сброса осадка из фильтра"
)

auger_m22 = Auger(
    start_signal=plc.DI_STATION19_START,
    manual_signal=plc.DI_STATION19_MANUAL,
    stop_signal=plc.DI_STATION19_STOP,
    output_signal=plc.DO_FLOWAUGER_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Шнек на переключатель потоков",
    slave_addr=14
)

fan_m12 = Auger(
    start_signal=plc.DI_STATION10_START,
    manual_signal=plc.DI_STATION10_MANUAL,
    stop_signal=plc.DI_STATION10_STOP,
    output_signal=plc.DO_FAN_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Вентилятор дымососа",
    slave_addr=4
)

# барабан сушильный

drum_m11 = Drum(
    start_signal=plc.DI_PANEL2_START,
    stop_signal=plc.DI_PANEL2_STOP,
    output_signal=plc.DO_DRUM_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Барабан сушильный"
)


plc.run(instances=[feeder_m1, izm_m2, drob_m4, groh_m6, drob_m15, groh_m17, conv_m3, 
                   conv_m5, conv_m7, conv_m8, conv_m10, conv_m14, conv_m16, conv_m18, 
                   conv_m19, conv_m20, auger_m13, auger_m22, fan_m12, drum_m11], ctx=globals())

