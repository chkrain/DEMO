from pyplc.utils.latch import RS
from pyplc.sfc import SFC, POU
from modbus import modbus_manager  # Исправляем импорт
import time

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
        self.last_modbus_call = 0
        
    def main(self):
        while True:
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
        # Защита от частых вызовов Modbus
        current_time = time.ticks_ms()
        if hasattr(self, 'last_modbus_call') and time.ticks_diff(current_time, self.last_modbus_call) < 100:
            return
        self.last_modbus_call = current_time
        
        try:
            if self.rs and self.rs.q:
                success1 = modbus_manager.write_register(
                    slave_addr=self.slave_addr, 
                    register_address=2, 
                    register_value=200
                )
                success2 = modbus_manager.write_register(
                    slave_addr=self.slave_addr, 
                    register_address=1, 
                    register_value=2178
                )
                if not success1 or not success2:
                    print(f"Ошибка записи в шнек {self.slave_addr}")
            else:
                success = modbus_manager.write_register(
                    slave_addr=self.slave_addr, 
                    register_address=1, 
                    register_value=2177
                )
                if not success:
                    print(f"Ошибка выключения шнека {self.slave_addr}")
                
        except Exception as e:
            print(f"Ошибка в шнеке {self.slave_addr}: {e}")