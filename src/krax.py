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

    cascade_start = POU.var(False)
    cascade_stop = POU.var(False)

    rstart = POU.var(False)
    rstop = POU.var(False)

    emergency_stop = POU.input(False)
    remergency = POU.var(False)
    
    def __init__(self, start_signal:bool, manual_signal=None, stop_signal=None, 
                 cascade_start=False, cascade_stop=False, emergency_stop = False,
                 output_signal=None, name=None, id: str = None, parent: POU = None):
        super().__init__(id=id, parent=parent)
        self.name = name or id or "Mechanism"
        
        # Инициализация сигналов
        self.start_signal = start_signal
        self.manual_signal = manual_signal
        self.stop_signal = stop_signal
        self.output_signal = output_signal
        self.name = name
        self.emergency_stop = emergency_stop

        self.cascade_start = cascade_start
        self.cascade_stop = cascade_stop

        self.rs = RS( )
        self.ton = TON(pt=3000) 
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
            set_condition = self.rstart and not self.emergency_stop and not self.remergency
            reset_condition = self.rstop or self.emergency_stop or self.remergency
        else:
            set_condition =  self.start_signal and not self.emergency_stop and not self.remergency
            reset_condition = not self.stop_signal or self.emergency_stop or self.remergency

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
    belt_break_true = POU.var(False)

    speed_percent = POU.var(float)

    rstart = POU.var(False)
    rstop = POU.var(False)

    emergency_stop = POU.input(False)
    remergency = POU.var(False)
    speed_value = POU.var(float)
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, emergency_stop = False,
                 output_signal=None, rope_switch_signal=None, belt_break_signal=None, belt_break_true = False,
                 name=None, slave_addr=1, speed_value=200, speed_percent=30.0,
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
        self.speed_percent = speed_percent
        self.emergency_stop = emergency_stop
        
        self.rs = RS()
        self.ready = False
        self.running = False
        self.last_belt_state = None
        self.belt_stuck_time = 0
        self.last_modbus_call = 0

        self.belt_break_true = belt_break_true
        self.speed_value = speed_value

        self._prev_speed_percent = speed_percent
        self._prev_speed_value = speed_value
        self._prev_rope_switch = rope_switch_signal
        self._prev_belt_break = belt_break_signal
        self._prev_output_state = None
        self._prev_start_signal = start_signal
        self._prev_stop_signal = stop_signal
        self._prev_manual_signal = manual_signal
        self._prev_output_signal = output_signal

        
    def main(self):
        while True:
            if self.manual_signal:
                set_condition = (self.start_signal and not self.emergency_stop and not self.remergency)
                    
                break_detected = self._check_belt_stuck()
                reset_conditions = [not self.stop_signal, self.rope_switch_signal, break_detected, self.emergency_stop, self.remergency]
                    
                reset_condition = any(reset_conditions)
            else:
                set_condition = (self.rstart and not self.emergency_stop and not self.remergency)
                break_detected = self._check_belt_stuck()
                reset_condition = (self.rstop or self.rope_switch_signal or break_detected or self.emergency_stop or self.remergency)
                
            self.rs(set=set_condition, reset=reset_condition)
            self.output_signal = self.rs.q
                
            if (self.output_signal != self._prev_output_state or
                self.speed_percent != self._prev_speed_percent or
                self.speed_value != self._prev_speed_value or
                self.rope_switch_signal != self._prev_rope_switch or
                self.belt_break_signal != self._prev_belt_break or
                self.start_signal != self._prev_start_signal or
                self.stop_signal != self._prev_stop_signal or 
                self.manual_signal != self._prev_manual_signal or
                self.output_signal != self._prev_output_signal):
                
                self._prev_output_state = self.output_signal
                self._prev_speed_percent = self.speed_percent
                self._prev_speed_value = self.speed_value
                self._prev_rope_switch = self.rope_switch_signal
                self._prev_belt_break = self.belt_break_signal
                self._prev_stop_signal = self.stop_signal
                self._prev_start_signal = self.start_signal
                self._prev_manual_signal = self.manual_signal
                self._prev_output_signal = self.output_signal
                
                self._frequency_control()
                
            yield
    
    def _frequency_control(self):
        target_speed = int(self.speed_value * self.speed_percent / 100)
        try:
            if self.rs.q:
                host.write_single_register(
                    slave_addr=self.slave_addr, 
                    register_address=2, 
                    register_value=target_speed
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
        except:
            pass
        
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
        
        time = 7000
        if self.speed_percent >= 80:
            time = 15000
        elif 50 <= self.speed_percent < 80:
            time = 35000
        elif 0 <= self.speed_percent < 50:
            time = 45000  
        
        result = (self.belt_stuck_time >= time) and self.rs.q

        if result:
            self.belt_break_true = True

        return result
    

class ConveyorPackaging(SFC):
    """Класс для конвейеров с частотным управлением"""
    
    start_signal = POU.input(False)
    manual_signal = POU.input(None)
    stop_signal = POU.input(False)
    output_signal = POU.output(False)
    rope_switch_signal = POU.input(False)
    belt_break_signal = POU.input(False)
    belt_break_true = POU.var(False)
    speed_percent = POU.var(float)
    rstart = POU.var(False)
    rstop = POU.var(False)
    speed_value = POU.var(float)
    gate = POU.input(True)
    emergency_stop = POU.input(False)
    remergency = POU.var(False)
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, emergency_stop = False,
                 output_signal=None, rope_switch_signal=None, belt_break_signal=None, belt_break_true = False,
                 name=None, slave_addr=1, speed_value=200, speed_percent=30.0, gate=True,
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
        self.speed_percent = speed_percent
        self.emergency_stop = emergency_stop
        
        self.rs = RS()
        self.ready = False
        self.running = False
        self.last_belt_state = None
        self.belt_stuck_time = 0
        self.last_modbus_call = 0

        self.belt_break_true = belt_break_true
        self.speed_value = speed_value

        self._prev_speed_percent = speed_percent
        self._prev_speed_value = speed_value
        self._prev_rope_switch = rope_switch_signal
        self._prev_belt_break = belt_break_signal
        self._prev_output_state = None
        self._prev_manual_signal = self.manual_signal
        self._prev_start_signal = self.start_signal
        self._prev_stop_signal = self.stop_signal
        self._prev_output_signal = self.output_signal

        self.gate = gate

        
    def main(self):
        while True:
            if self.manual_signal:
                set_condition = (self.start_signal and not self.gate and not self.emergency_stop and not self.remergency)
                    
                break_detected = self._check_belt_stuck()
                reset_conditions = [not self.stop_signal, self.gate, self.rope_switch_signal, break_detected, self.emergency_stop, self.remergency]
                    
                reset_condition = any(reset_conditions)
            else:
                set_condition = (self.rstart or not self.gate and not self.emergency_stop and not self.remergency)
                break_detected = self._check_belt_stuck()
                reset_condition = (self.rstop or self.rope_switch_signal or break_detected or self.gate or self.emergency_stop or self.remergency)
                
            self.rs(set=set_condition, reset=reset_condition)
            self.output_signal = self.rs.q
                
            if (self.output_signal != self._prev_output_state or
                self.speed_percent != self._prev_speed_percent or
                self.speed_value != self._prev_speed_value or
                self.rope_switch_signal != self._prev_rope_switch or
                self.belt_break_signal != self._prev_belt_break or
                self.start_signal != self._prev_start_signal or
                self.stop_signal != self._prev_stop_signal or 
                self.manual_signal != self._prev_manual_signal or
                self.output_signal != self._prev_output_signal):
                
                self._prev_output_state = self.output_signal
                self._prev_speed_percent = self.speed_percent
                self._prev_speed_value = self.speed_value
                self._prev_rope_switch = self.rope_switch_signal
                self._prev_belt_break = self.belt_break_signal
                self._prev_stop_signal = self.stop_signal
                self._prev_start_signal = self.start_signal
                self._prev_manual_signal = self.manual_signal
                self._prev_output_signal = self.output_signal
                
                self._frequency_control()
                
            yield
    
    def _frequency_control(self):
        target_speed = int(self.speed_value * self.speed_percent / 100)
        try:
            if self.rs.q:
                host.write_single_register(
                    slave_addr=self.slave_addr, 
                    register_address=2, 
                    register_value=target_speed
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
        except:
            pass
        
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
        
        time = 7000
        if self.speed_percent >= 80:
            time = 15000
        elif 50 <= self.speed_percent < 80:
            time = 35000
        elif 0 <= self.speed_percent < 50:
            time = 45000  
        
        result = (self.belt_stuck_time >= time) and self.rs.q

        if result:
            self.belt_break_true = True

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
    speed_value = POU.var(float)
    speed_percent = POU.var(float)
    belt_break_true = POU.var(False)
    rstart = POU.var(False)
    rstop = POU.var(False)
    remergency = POU.var(False)
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, panel_start=None, panel_stop=None,
                 output_signal=None, rope_switch_signal=None, belt_break_signal=None, belt_break_true = False,
                 name=None, slave_addr=1, speed_value=0.0, speed_percent=30.0, emergency_stop = False,
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
        self.speed_value = speed_value
        self.speed_percent = speed_percent
        self.belt_break_true = belt_break_true
        self.rs = RS()
        self.ready = False
        self.running = False
        self.last_belt_state = None
        self.belt_stuck_time = 0
        self._prev_panel_start = panel_start
        self._prev_panel_stop = panel_stop
        self._prev_output_state = None
        self._prev_speed_percent = speed_percent
        self._prev_speed_value = speed_value
        self._prev_rope_switch = rope_switch_signal
        self._prev_belt_break = belt_break_signal
        self._prev_panel_start = panel_start
        self._prev_panel_stop = panel_stop
        self._prev_manual_signal = self.manual_signal
        self._prev_start_signal = self.start_signal
        self._prev_stop_signal = self.stop_signal
        self._prev_output_signal = self.output_signal
        self.emergency_stop = emergency_stop
        
    def main(self):
        if self.manual_signal:
            set_condition = (self.start_signal or self.panel_start and not self.emergency_stop and not self.remergency)
            
            break_detected = self._check_belt_stuck()
            reset_conditions = [not self.stop_signal, not self.panel_stop, self.rope_switch_signal, break_detected, self.emergency_stop, self.remergency]
                    
            reset_condition = any(reset_conditions)
        else:
            set_condition = (self.rstart or self.panel_start and not self.emergency_stop and not self.remergency)
            break_detected = self._check_belt_stuck()
            reset_condition = (self.rstop or self.rope_switch_signal or break_detected or not self.panel_stop or self.emergency_stop or self.remergency)
            
        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q
            
        if (self.output_signal != self._prev_output_state or
            self.speed_percent != self._prev_speed_percent or
            self.speed_value != self._prev_speed_value or
            self.rope_switch_signal != self._prev_rope_switch or
            self.belt_break_signal != self._prev_belt_break or
            self.panel_start != self._prev_panel_start or
            self.panel_stop != self._prev_panel_stop or           
            self.start_signal != self._prev_start_signal or
            self.stop_signal != self._prev_stop_signal or 
            self.manual_signal != self._prev_manual_signal or
            self.output_signal != self._prev_output_signal):
            
            self._prev_output_state = self.output_signal
            self._prev_speed_percent = self.speed_percent
            self._prev_speed_value = self.speed_value
            self._prev_rope_switch = self.rope_switch_signal
            self._prev_belt_break = self.belt_break_signal
            self._prev_panel_start = self.panel_start
            self._prev_panel_stop = self.panel_stop
            self._prev_stop_signal = self.stop_signal
            self._prev_start_signal = self.start_signal
            self._prev_manual_signal = self.manual_signal
            self._prev_output_signal = self.output_signal
            
            self._frequency_control()
            
        yield
    
    def _frequency_control(self):
        target_speed = int(self.speed_value * self.speed_percent / 100)
        try:
            if self.rs.q:
                host.write_single_register(
                    slave_addr=self.slave_addr, 
                    register_address=2, 
                    register_value=target_speed
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
        except:
            pass
        
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
        
        time = 7000
        if self.speed_percent >= 80:
            time = 15000
        elif 50 <= self.speed_percent < 80:
            time = 35000
        elif 0 <= self.speed_percent < 50:
            time = 45000  
        
        result = (self.belt_stuck_time >= time) and self.rs.q

        if result:
            self.belt_break_true = True

        return result

class Auger(SFC):
    start_signal = POU.input(False)
    manual_signal = POU.input(False)
    stop_signal = POU.input(False)
    output_signal = POU.output(False)

    rstart = POU.var(False)
    rstop = POU.var(False)

    speed_value = POU.var(float)
    speed_percent = POU.var(float)

    emergency_stop = POU.input(False)
    remergency = POU.var(False)
    
    def __init__(self, start_signal=None, manual_signal=None, stop_signal=None, 
                 output_signal=None, name=None, slave_addr=1, emergency_stop = False,
                 speed_value=0.0, speed_percent=100.0,
                 id: str = None, parent: POU = None):
        
        super().__init__(id=id, parent=parent)
        
        self.name = name or id or "Auger"
        self.slave_addr = slave_addr
        
        self.start_signal = start_signal
        self.manual_signal = manual_signal
        self.stop_signal = stop_signal
        self.output_signal = output_signal

        self.speed_value = speed_value
        self.speed_percent = speed_percent
        self.emergency_stop = emergency_stop

        self._prev_output_state = None
        self._prev_speed_percent = speed_percent
        self._prev_speed_value = speed_value
        self._prev_start_signal = start_signal
        self._prev_stop_signal = stop_signal
        self._prev_manual_signal = manual_signal
        self._prev_output_signal = output_signal
        
        self.rs = RS()

        
    def main(self):
        if self.manual_signal:
            set_condition = self.start_signal and not self.emergency_stop and not self.remergency
            reset_condition = not self.stop_signal or self.emergency_stop or self.remergency
        else:
            set_condition = self.rstart and not self.emergency_stop and not self.remergency
            reset_condition = self.rstop or self.emergency_stop or self.remergency
            
        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q
            
        if (self.output_signal != self._prev_output_state or
            self.speed_percent != self._prev_speed_percent or
            self.speed_value != self._prev_speed_value or        
            self.start_signal != self._prev_start_signal or
            self.stop_signal != self._prev_stop_signal or 
            self.manual_signal != self._prev_manual_signal or
            self.output_signal != self._prev_output_signal):
            
            self._prev_output_state = self.output_signal
            self._prev_speed_percent = self.speed_percent
            self._prev_speed_value = self.speed_value
            self._prev_stop_signal = self.stop_signal
            self._prev_start_signal = self.start_signal
            self._prev_manual_signal = self.manual_signal
            self._prev_output_signal = self.output_signal
            
            self._frequency_control()
            
        yield
    
    def _frequency_control(self):
        target_speed = int(self.speed_value * self.speed_percent / 100)
        try:
            if self.rs.q:
                host.write_single_register(
                    slave_addr=self.slave_addr, 
                    register_address=2, 
                    register_value=target_speed
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
        except:
            pass

class Drum(SFC):
    start_signal = POU.input(False)
    stop_signal = POU.input(False)
    output_signal = POU.output(False)

    rstart = POU.var(False)
    rstop = POU.var(False)
    remergency = POU.var(False)

    emergency_stop = POU.input(False)
    
    def __init__(self, start_signal=None, stop_signal=None, 
                 output_signal=None, name=None, emergency_stop=False,
                 id: str = None, parent: POU = None):
        
        super().__init__(id=id, parent=parent)
        
        self.name = name or id or "Drum"
        
        # Инициализация сигналов
        self.start_signal = start_signal
        self.stop_signal = stop_signal
        self.emergency_stop = emergency_stop
        self.output_signal = output_signal
        

        
        self.rs = RS()

        
    def main(self):
        set_condition = self.start_signal or self.rstart and not self.emergency_stop and not self.remergency
        reset_condition = not self.stop_signal or self.rstop or self.emergency_stop or self.remergency
            
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
    rope_switch_signal=plc.DI_BELTFEEDER_ROPESWITCH_TRIPPED,
    belt_break_signal=plc.DI_BELTFEEDER_BELTBREAK_TRIPPED,
    panel_start=plc.DI_PANEL1_START,      
    panel_stop=plc.DI_PANEL1_STOP,     
    name="Питатель M1",
    slave_addr=1,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    speed_value=1500
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
    slave_addr=2,
    speed_value=1500
)

conv_m5 = Conveyor(
    start_signal=plc.DI_STATION5_START,
    manual_signal=plc.DI_STATION5_MANUAL,
    stop_signal=plc.DI_STATION5_STOP,
    output_signal=plc.DO_CONVEYOR6506000_BOLT_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6506000_ROPESWITCH_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6506000_BELTBREAK_TRIPPED,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name='Конвейер на грохот M6',
    slave_addr=9,
    speed_value=1500
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
    slave_addr=10,
    speed_value=1500
)

conv_m8 = ConveyorPackaging(
    start_signal=plc.DI_STATION8_START,
    manual_signal=plc.DI_STATION8_MANUAL,
    stop_signal=plc.DI_STATION8_STOP,
    output_signal=plc.DO_CONVEYOR6506000_PACKING_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR6506000_ROPESWITCH3_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR6506000_BELTBREAK3_TRIPPED,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name='Конвейер на станцию фасовки',
    slave_addr=11,
    gate=plc.DI_PACKINGHOPPERGATE_OPEN,
    speed_value=1500
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
    slave_addr=3,
    speed_value=1500
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
    slave_addr=5,
    speed_value=1500
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
    slave_addr=6,
    speed_value=1500
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
    slave_addr=12,
    speed_value=1500
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
    slave_addr=13,
    speed_value=1500
)

conv_m20 = ConveyorPackaging(
    start_signal=plc.DI_STATION18_START,
    manual_signal=plc.DI_STATION18_MANUAL,
    stop_signal=plc.DI_STATION18_STOP,
    output_signal=plc.DO_CONVEYOR6501000_PACKING_TURNON,
    rope_switch_signal=plc.DI_CONVEYOR65010000_ROPESWITCH2_TRIPPED,
    belt_break_signal=plc.DI_CONVEYOR65010000_BELTBREAK2_TRIPPED,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Конвейер M20 на станцию фасовки",
    gate=plc.DI_PACKINGHOPPERGATE2_OPEN,
    slave_addr=7,
    speed_value=1500
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
    name="Вентилятор дымососа",
    slave_addr=4,
    speed_value=1500
)

# барабан сушильный

drum_m11 = Drum(
    start_signal=plc.DI_PANEL2_START,
    stop_signal=plc.DI_PANEL2_STOP,
    output_signal=plc.DO_DRUM_TURNON,
    emergency_stop=plc.DI_EMERGENCY_STOP,
    name="Барабан сушильный"
)


class CascadeController(SFC):
    """Контроллер каскадного управления"""
    
    IDLE = 0
    STARTING = 1
    STOPPING = 2
    
    on = POU.var(False)
    off = POU.var(False)
    msg = POU.var('ГОТОВ')

    def __init__(self, equipment_list: list, id: str = None, parent: POU = None):
        super().__init__(id=id, parent=parent)
        self.equipment_list = equipment_list
        self._t_on = FTRIG(clk=lambda: self.on)
        self._t_off = RTRIG(clk=lambda: self.off)
        self.subtasks = (self._t_on, self._t_off)
        self.state = CascadeController.IDLE

    def _start(self):
        """Последовательный запуск оборудования"""
        self.state = CascadeController.STARTING
        self.msg = 'ЗАПУСК КАСКАДА'
        print('=== НАЧАЛО ЗАПУСКА КАСКАДА ===')
        
        for i, equipment in enumerate(self.equipment_list):
            print(f'ШАГ {i+1}/{len(self.equipment_list)}: Запуск {equipment.id}')
            
            if hasattr(equipment, 'output_signal') and equipment.output_signal:
                print(f'  {equipment.id} уже запущен, пропускаем')
                continue
            
            print(f'  Подаем команду запуска на {equipment.id}')
            if hasattr(equipment, 'rstart'):
                equipment.rstart = True
                yield
                equipment.rstart = False
            
            # Ждем запуска оборудования
            print(f'  Ожидаем запуска {equipment.id}')
            timeout = TON(pt=5000)  # 5 секунд на запуск каждого оборудования
            start_time = 0
            while start_time < 5000:
                timeout(True)
                if timeout.q:
                    print(f'  ТАЙМАУТ: {equipment.id} не запустился за 5 секунд')
                    break
                if hasattr(equipment, 'output_signal') and equipment.output_signal:
                    print(f'  {equipment.id} успешно запущен')
                    break
                yield from self.pause(100)
                start_time += 100
            
            if not (hasattr(equipment, 'output_signal') and equipment.output_signal):
                print(f'  ОШИБКА: Не удалось запустить {equipment.id}')
                self.msg = f'ОШИБКА ЗАПУСКА {equipment.id}'
                self.state = CascadeController.IDLE
                return
            
            if self.state != CascadeController.STARTING:
                print('  Запуск прерван')
                break
            
            if i < len(self.equipment_list) - 1:
                print(f'  Пауза 5 секунды перед следующим оборудованием')
                yield from self.pause(5000)
        
        if self.state == CascadeController.STARTING:
            self.state = CascadeController.IDLE
            self.msg = 'КАСКАД ЗАПУЩЕН'
            print('=== КАСКАД УСПЕШНО ЗАПУЩЕН ===')

    def _stop(self):
        """Последовательная остановка оборудования"""
        self.state = CascadeController.STOPPING
        self.msg = 'ОСТАНОВ КАСКАДА'
        print('=== НАЧАЛО ОСТАНОВА КАСКАДА ===')
        
        for i, equipment in enumerate(reversed(self.equipment_list)):
            eq_index = len(self.equipment_list) - i - 1
            print(f'ШАГ {i+1}/{len(self.equipment_list)}: Остановка {equipment.id}')
            
            if not (hasattr(equipment, 'output_signal') and equipment.output_signal):
                print(f'  {equipment.id} уже остановлен, пропускаем')
                continue
            
            print(f'  Подаем команду остановки на {equipment.id}')
            if hasattr(equipment, 'rstop'):
                equipment.rstop = True
                yield
                equipment.rstop = False
            
            # Ждем остановки оборудования
            print(f'  Ожидаем остановки {equipment.id}')
            timeout = TON(pt=5000)  # 5 секунд на остановку каждого оборудования
            stop_time = 0
            while stop_time < 5000:
                timeout(True)
                if timeout.q:
                    print(f'  ТАЙМАУТ: {equipment.id} не остановился за 5 секунд')
                    break
                if not (hasattr(equipment, 'output_signal') and equipment.output_signal):
                    print(f'  {equipment.id} успешно остановлен')
                    break
                yield from self.pause(100)
                stop_time += 100
            
            if hasattr(equipment, 'output_signal') and equipment.output_signal:
                print(f'  ОШИБКА: Не удалось остановить {equipment.id}')
                self.msg = f'ОШИБКА ОСТАНОВА {equipment.id}'
                self.state = CascadeController.IDLE
                return
            
            if self.state != CascadeController.STOPPING:
                print('  Останов прерван')
                break
            
            if i < len(self.equipment_list) - 1:
                print(f'  Пауза 5 секунды перед следующим оборудованием')
                yield from self.pause(5000)
        
        if self.state == CascadeController.STOPPING:
            self.state = CascadeController.IDLE
            self.msg = 'КАСКАД ОСТАНОВЛЕН'
            print('=== КАСКАД УСПЕШНО ОСТАНОВЛЕН ===')

    def main(self):
        print('Каскадный контроллер запущен. Ожидание команд...')
        
        while True:
            yield from self.until(lambda: self._t_on.q or self._t_off.q, step='ожидаем пуск/стоп')
            
            if self._t_on.q and self.state == CascadeController.IDLE:
                print('Получена команда ЗАПУСКА каскада')
                yield from self._start()
            
            if self._t_off.q and self.state == CascadeController.IDLE:
                print('Получена команда ОСТАНОВА каскада')
                yield from self._stop()
            
            yield

cascade_equipment = [
    conv_m19,
    conv_m18,  
    groh_m17, 
    conv_m16,
    drob_m15,
    conv_m14,
    auger_m13, 
    drum_m11, 
    conv_m10, 
    conv_m7,  
    groh_m6, 
    conv_m5,
    drob_m4,
    conv_m3, 
    izm_m2, 
    feeder_m1
]

cascade_controller = CascadeController(
    equipment_list=cascade_equipment,
    id="Каскадный контроллер"
)

class Emergency(SFC):
    emergency_signal = POU.input(False) 
    
    def __init__(self, equipment_list: list, id: str = None, parent: POU = None):
        super().__init__(id=id, parent=parent)
        self.equipment_list = equipment_list
        self._prev_emergency = False

    def main(self):
        while True:
            current_emergency = self.emergency_signal
        
            if current_emergency != self._prev_emergency:
                action = True if current_emergency else False
                print("!!! АВАРИЙНАЯ ОСТАНОВКА !!!" if action else "Аварийная остановка снята")
            
                for equipment in self.equipment_list:
                    if hasattr(equipment, 'remergency'):
                        equipment.remergency = action
            
                self._prev_emergency = current_emergency
        
            yield

all_equipment = [
    feeder_m1, izm_m2, conv_m3, drob_m4, conv_m5, groh_m6, conv_m7, 
    conv_m8, conv_m10, auger_m13, conv_m14, drob_m15, conv_m16, 
    groh_m17, conv_m18, conv_m19, conv_m20, drum_m11
]


emerg = Emergency(
    equipment_list=all_equipment
)

plc.run(instances=[feeder_m1, izm_m2, drob_m4, groh_m6, drob_m15, groh_m17, conv_m3, 
                   conv_m5, conv_m7, conv_m8, conv_m10, conv_m14, conv_m16, conv_m18, 
                   conv_m19, conv_m20, auger_m13, auger_m22, drum_m11, cascade_controller, fan_m12, emerg], ctx=globals())

