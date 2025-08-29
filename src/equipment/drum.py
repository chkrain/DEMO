from pyplc.utils.latch import RS
from pyplc.sfc import SFC, POU

class Drum(SFC):
    start_signal = POU.input(False)
    stop_signal = POU.input(False)
    output_signal = POU.output(False)

    emergency_stop = POU.input(False, hidden=True)

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
        while True:
            set_condition = self.start_signal or self.rstart
            reset_condition = not self.stop_signal or self.rstop or self.emergency_stop
            
            self.rs(set=set_condition, reset=reset_condition)
            self.output_signal = self.rs.q
            
            yield