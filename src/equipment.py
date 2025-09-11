from pyplc.sfc import SFC, POU
from pyplc.utils.latch import RS
from pyplc.utils.trig import TRIG, FTRIG, RTRIG
from pyplc.utils.misc import TOF

class Equipment(SFC):
    """ Базовый класс для работы с оборудованием: конвейера, механизмы"""
    IDLE    = 0
    STARTUP = 1
    RUN     = 2
    STOP    = 3

    ready       = POU.var(False)
    on          = POU.var(False)
    off         = POU.var(False)
    start       = POU.input(False, hidden=True)
    stop        = POU.input(False, hidden=True)
    manual      = POU.input(False)
    block       = POU.var(False)
    starting    = POU.var(int(1), persistent=True) # 1 sec
    test_on     = POU.var(False)
    test_alarm  = POU.var(int(0))
    override    = POU.var(False, persistent=True)

    fault       = POU.input(False)
    lock        = POU.input(False)
    q           = POU.output(False)
    msg         = POU.var('Ожидание команд')


    def __init__(self, id = None, parent = None, fault = None, q = None, lock = None, depends = None, start = None, stop = None, manual = None):
        super().__init__(id, parent)
        self.state      = Equipment.IDLE
        self.allowed    = True
        self.fault      = fault
        self.lock       = lock
        self.depends    = self._ensure_tuple(depends)
        self._ctl       = RS(reset = self.set_stop, set = self.set_start, q = self.control)
        self._tst       = FTRIG(clk = lambda: self.test_on, q = self._test)
        self.subtasks   = (self._ctl, self._tst)
        self._pass      = 0
        self.q          = q

    def _test(self, on):
        if on:
            if self.test_alarm == 0:
                self.inspect(fault = lambda x: x.force(True if self._pass == 0 else None))
            elif self.test_alarm == 1:
                self.inspect(lock = lambda x: x.force(True if self._pass == 0 else None))
        else:
            self._pass = (self._pass + 1) % 2

    def _ensure_tuple(self, value):
        return value if value is None or isinstance(value, tuple) else (value,)


    def set_start(self):
        self.msg = 'сет старт'
        return self.start if self.manual else self.on
        
    def set_stop(self):
        self.msg = 'сет стоп'
        return self.stop if self.manual else self.off
        
    def _turnon(self):
        self.block = False

    def _turnoff(self):
        self.allowed = True

    def _allowed(self):
        self.allowed = True
        if self.depends is not None and not self.manual:
            for dep in self.depends:
                if dep.state != Equipment.RUN:
                    return False
                if dep.fault: 
                    self.allowed = False
        else:
            self.allowed = not self.lock

        if self.lock:
            self.allowed = False
            return self.allowed 
        
        return self.allowed
        
    def control(self, power):
        self.msg = 'Зашли в контрол'
        if power and not self._allowed():
            self.block = True
            return
        self.q = power and not self.lock
        if power and self.lock:
            self.block = True
        if not power:
            self.lock = False

    def _begin(self):
        self.msg = 'Работа начата'

    def _end(self):
        self.msg = 'Работа завершена'
    
    def main(self):
        self.msg = 'Начало работы'
        self.state  = Equipment.IDLE
        self.ready  = False
        self.busy   = False
        self.msg = 'Ожидание старта'
        yield from self.until(lambda: self.q, step = "waiting start")

        self.msg = 'Старт получен, запускаемся'

        self.state = Equipment.STARTUP
        self._turnon()
        t = 0
        while t < self.starting and not self.fault and self._allowed():
            yield from self.pause(1000)
            t += 1
            self.ready = not self.ready
        
        if t < self.starting:
            self.ready = False
            if self.q and self.fault:
                self.log('alarm stop after starting')
        else:
            self.ready = True
            self.state = Equipment.RUN
            self._begin()
            yield from self.till(lambda: self.q and self._allowed() and not self.lock, step = 'working')
            self._end()

        self._turnoff()
        self._ctl.unset()
        self.state  = Equipment.STOP
        self.busy   = False
        self.ready  = False
        if self.lock:
            self.log('disabled -> lock')
            self.block = True

        self.q = False
                
class EquipmentROT(Equipment):
    """Класс для управления оборудованием с датчиком вращения (конвейера, шнеки)"""
    rotating = POU.var(False)
    rot = POU.input(False, hidden = True)
    
    def __init__(self, fault: bool = None, q: bool = None, lock: bool = None, rot: bool = None, depends: Equipment = None, id: str = None, parent: POU = None, start = None, stop = None, manual = None):
        super().__init__(fault=fault, q=q, lock=lock, depends=depends, id=id, parent=parent)
        self.rot = rot
        self._rotating = TOF(clk = TRIG(clk = lambda: self.rot), q = self.monitor)
        self.subtasks += (self._rotating, )


    def monitor(self, rot: bool):
        self.rotating = rot
        if not rot and self.q:
            self.ok = False
            self.log('ошибка: нет вращения')

    def set_timeout(self, speed_value=1500):
        if      speed_value < 500:  self._rotating.pt = 35000
        elif    speed_value < 1000: self._rotating.pt = 25000
        elif    speed_value < 1500: self._rotating.pt = 15000
        else:                       self._rotating.pt = 35000

class EquipmentFeeder(EquipmentROT):
    pult_start = POU.input(False)
    pult_stop  = POU.input(False)
    
    def __init__(self, pult_start=None, pult_stop=None, **kwargs):
        super().__init__(**kwargs)
        self.pult_start = pult_start
        self.pult_stop = pult_stop
        
        self._pult_start_trig = RTRIG(clk=lambda: self.pult_start)
        self._pult_stop_trig = RTRIG(clk=lambda: self.pult_stop)
        
        self.subtasks += (self._pult_start_trig, self._pult_stop_trig)
    
    def set_start(self):
        base = super().set_start()
        if hasattr(self, '_pult_start_trig'):
            return base or self._pult_start_trig.q
        return base
        
    def set_stop(self):
        base = super().set_stop()
        if hasattr(self, '_pult_stop_trig'):
            return base or self._pult_stop_trig.q
        return base

class EquipmentDrum(Equipment):
    def __init__(self, q=None, depends=None, start=None, stop=None, fault=None, **kwargs):
        super().__init__(q=q, depends=depends, start=start, stop=stop, 
                        manual=None, fault=fault, **kwargs)
    
    def set_start(self):
        return self.on
        
    def set_stop(self):
        return self.off

class EquipmentPack(EquipmentROT):
    gate = POU.input(False)
    
    def __init__(self, gate=None, **kwargs):
        super().__init__(**kwargs)
        self.gate = gate
    
    def set_start(self):
        base_start = super().set_start()
        
        if self.manual:
            result = self.gate and base_start
            print(f'Ручной: gate={self.gate}, base={base_start} -> {result}')
        else:
            result = self.gate or base_start
            print(f'Авто: gate={self.gate}, base={base_start} -> {result}')
        
        return result
    
    def set_stop(self):
        base_stop = super().set_stop()
        return not self.gate or base_stop
    
    def _allowed(self):
        self.allowed = True
        
        if self.depends is not None and not self.manual:
            for dep in self.depends:
                if dep.state != Equipment.RUN:
                    return False
                if dep.fault: 
                    self.allowed = False
        
        self.allowed = not self.lock
        
        return self.allowed

    
class EquipmentAutoStart(Equipment):
    def __init__(self, auto_start_on=None, **kwargs):
        self.auto_start_on = self._ensure_tuple(auto_start_on)
        super().__init__(**kwargs)
        self._dummy = TOF(clk=lambda: False, pt=1000)
        self.subtasks += (self._dummy,)
    
    def set_start(self):
        base_start = super().set_start()
        
        auto_start = False
        if self.auto_start_on is not None and not self.manual:
            for equipment in self.auto_start_on:
                if equipment.state == Equipment.RUN:
                    auto_start = True
                    break
        
        return base_start or auto_start

    
class EquipmentROTAutoStart(EquipmentROT):
    def __init__(self, auto_start_on=None, **kwargs):
        self.auto_start_on = self._ensure_tuple(auto_start_on)
        super().__init__(**kwargs)
    
    def set_start(self):
        base_start = super().set_start()
        
        auto_start = False
        if self.auto_start_on is not None and not self.manual:
            for equipment in self.auto_start_on:
                if equipment.state == Equipment.RUN:
                    auto_start = True
                    break
        
        return base_start or auto_start

class EquipmentChain(SFC):
    IDLE        = 0
    STARTING    = 1
    STOPPING    = 2
    UNDEFINED   = 3
    EMERGENCY   = 4

    on      = POU.var(False)
    off     = POU.var(False)
    msg     = POU.var('ГОТОВ')
    emerg   = POU.var(False)

    def __init__(self, gears: tuple[Equipment], id: str = None, parent: POU = None) -> None:
        super().__init__( id=id, parent=parent)
        self.gears = gears
        self._t_on = FTRIG(clk = lambda: self.on )
        self._t_off= RTRIG(clk = lambda: self.off )
        self._t_emerg=FTRIG(clk=lambda: self.emerg)
        self.subtasks = (self._t_on, self._t_off, self._t_emerg)
        self.state = EquipmentChain.IDLE

    def _countdown(self, gear, action, total_time, condition):
        """Универсальная функция обратного отсчета"""
        remaining = total_time
        if not condition: return
        while remaining >= 0:
            self.msg = f'{action} {gear.id}: {remaining} сек' # </bold>
            yield from self.pause(1000)
            remaining -= 1
        self.msg = f'Оборудование {gear.id} отработано, переход к следующему..'
        return remaining == 0

    def _start(self):
        self.state = EquipmentChain.STARTING
        for gear in self.gears:
            if gear.state == Equipment.RUN:
                continue
            if gear.lock:
                gear.off = True
                yield
                gear.off = False
            gear.on = True
            yield
            gear.on = False
            yield from self.till(lambda: gear.state != Equipment.RUN and self.state == EquipmentChain.STARTING, max=5000, step=f'ожидаем запуска {gear.id}') and \
            self._countdown(gear, 'Каскадный пуск', gear.starting, lambda: gear.state != Equipment.RUN and self.state == EquipmentChain.STARTING)
            if gear.state!= Equipment.RUN:
                self.msg=f'Неудачная попытка запуска {gear.id}'
                return
            if self.state != EquipmentChain.STARTING:
                break
            yield from self.pause(2000)
        if self.state==EquipmentChain.STARTING: 
            self.state = EquipmentChain.IDLE
            self.msg = 'ГОТОВ | Ожидание команды'

    def _stop(self):
        self.state = EquipmentChain.STOPPING
        for gear in reversed(self.gears):
            if gear.state == Equipment.IDLE:
                continue
            yield from self.till(lambda: gear.state == Equipment.RUN and self.state==EquipmentChain.STOPPING, max = gear.starting*1000, step = f'штатный останов {gear.id}') and \
            self._countdown(gear, 'ОСТАНОВ', gear.starting, lambda: gear.state == Equipment.RUN and self.state == EquipmentChain.STOPPING)            
            gear.off = True
            yield
            gear.off = False
            yield from self.till(lambda: gear.state != Equipment.IDLE and self.state==EquipmentChain.STOPPING, step=f'ожидаем остановки {gear.id}',max = 2000)
            if gear.state != Equipment.IDLE:
                self.msg=f'Неудачная попытка остановки {gear.id}'
                return
            if self.state != EquipmentChain.STOPPING:break
            yield from self.pause(2000)
        if self.state==EquipmentChain.STOPPING: 
            self.state = EquipmentChain.IDLE
            self.msg = 'ГОТОВ'

    def _emergency(self):
        self.state = EquipmentChain.EMERGENCY
        for gear in self.gears:
            gear.off = True

    def _emergency_off(self):
        self.state = EquipmentChain.IDLE
        for gear in self.gears:
            gear.off = False


    def main(self):
        yield from self.until(lambda: self._t_on.q or self._t_off.q or self._t_emerg, step='ожидаем пуск/стоп/emerg')
        
        if self.emerg and not self.state == EquipmentChain.EMERGENCY:
            self._emergency()
            self.emerg = False
            self.msg='ВЫЗВАНА АВАРИЙНАЯ ОСТАНОВКА'

        if self.emerg and self.state == EquipmentChain.EMERGENCY:
            self._emergency_off()
            self.emerg = False
            self.msg='ОТМЕНА АВАРИЙНОЙ ОСТАНОВКИ | Ожидание команд'

        if self._t_on.q:
            if self.state!=EquipmentChain.STARTING:
                self.msg='Последовательный запуск активирован'
                self.exec(self._start())
            else:
                self.state=EquipmentChain.IDLE
        elif self._t_off.q:
            if self.state!=EquipmentChain.STOPPING:
                self.msg='Последовательный останов активирован'
                self.exec(self._stop() )
            else:
                self.state=EquipmentChain.IDLE