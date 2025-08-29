from pyplc.platform import plc
from pyplc.utils.latch import RS
from pyplc.sfc import SFC, POU

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
    
    def auto_ctl(self, x: bool):
        if not self.manual: return
        self.q = x
        
    def main(self):
        # Базовая логика для механизмов
        if not self.manual_signal:
            set_condition = self.rstart
            reset_condition = self.rstop or self.emergency_stop
            print('Test', 'Ok')
        elif self.manual_signal:
            set_condition =  self.start_signal 
            reset_condition = not self.stop_signal
        
        self.rs(set=set_condition, reset=reset_condition)
        self.output_signal = self.rs.q

        yield