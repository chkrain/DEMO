from pyplc.sfc import SFC,POU
from pyplc.utils.misc import BLINK,TON
from typing import Any

class IValveOrCylinder(SFC):
    open = POU.input(False,hidden=True)
    closed = POU.output(False,hidden=True)
    def __init__(self, open: bool, closed: bool):
        super().__init__(id='_', parent=None)
        self.open  = open
        self.closed=closed.force if hasattr(closed,'force') else closed
        
    def main(self):
        while True:
            if self.open:
                if self.closed:
                    yield from self.pause(1000)
                self.closed = False
                yield from self.till(lambda: self.open)
                yield from self.until(lambda: self.open,max=1000)
                if not self.open:
                    self.closed = True
            else:
                self.closed = True
                
            yield
            
class IRotation(POU):
    q = POU.input(False,hidden=True)
    rot = POU.output(False,hidden=True)
    def __init__(self, q: bool | Any = None, rot:bool | Any  = None, id: str | Any = None, parent: POU | Any = None) -> None:
        super().__init__(id, parent)
        self.rot=rot.force if hasattr(rot,'force') else rot
        self.blink = BLINK(enable = q,q = IRotation.rot(self), t_on = 100, t_off = 500 )
        
    def __call__(self):
        with self:
            self.blink( )
            
class IMotor(POU):
    q = POU.input(False,hidden=True)
    ison = POU.output(False,hidden=True)

    def __init__(self, q: bool | Any = None, ison:bool | Any  = None, id: str | Any = None, parent: POU | Any = None) -> None:
        super().__init__(id, parent)
        self.ison=ison.force if hasattr(ison,'force') else ison
        self.powered = TON(clk=q, q=IMotor.ison(self),pt=2000)
        
        
    def __call__(self):
        with self:
            self.powered( )

class IPressure(POU):
    fq = POU.input(int(0),hidden=True)
    pressure  = POU.output(int(0),hidden=True)
    
    def __init__(self, fq, pressure,en, id: str = None, parent: POU = None) -> None:
        super().__init__(id, parent)
        self._last = 0
        self.pressure = pressure.force if hasattr(pressure,'force') else pressure
        self.fq = fq
        self.en = en
        self._integral = 0
        
    def __call__(self):
        with self:
            if self.en:
                self.pressure = int(self.fq * 0.4 + self._integral)
                self._integral += (self.fq - self.pressure)*0.01
            else:
                self.pressure = max(self.pressure - 10, 0)
                self._integral = 0

class IGate(POU):
    def __init__(self, equipment, simulate=True, id=None, parent=None):
        super().__init__(id, parent)
        self.equipment = equipment
        self.simulate = simulate
        
    def __call__(self):
        with self:
            if self.simulate:
                self.equipment.gate = True