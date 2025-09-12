from pyplc.sfc import SFC, POU
from pyplc.utils.latch import RS
from pyplc.utils.trig import TRIG, FTRIG, RTRIG
from pyplc.utils.misc import TOF
from _thread import start_new_thread,allocate_lock
from umodbus.tcp import TCP as ModbusTCPMaster
import time

class ModbusClient:
    _instance   = None
    _lock       = allocate_lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance           = super().__new__(cls)
            cls._instance.host      = None
            cls._instance.queue     = []
            cls._instance.running   = True
            cls._instance.connected = False
            start_new_thread(cls._instance._worker, ())
        return cls._instance
    
    def _connect(self):
        if self.connected and self.host:
            return True
            
        try:
            self.host       = ModbusTCPMaster(slave_ip='192.168.8.10', slave_port=502, timeout=3)
            self.connected  = True
            print("Модбас подключен")
            return True
        except Exception as e:
            print(f"Ошибка модбас: {e}")
            self.host       = None
            self.connected  = False
            return False
    
    def write_register(self, slave_addr, register_address, register_value):
        with self._lock:
            self.queue.append(('write', slave_addr, register_address, register_value))
    
    def _worker(self):
        while self.running:
            try:
                if not self.connected:
                    self._connect()
                    time.sleep(2)
                    continue
                
                if self.queue and self.connected:
                    with self._lock:
                        task = self.queue.pop(0)
                    
                    if task[0] == 'write' and self.host:
                        try:
                            result = self.host.write_single_register(slave_addr=task[1], register_address=task[2], register_value=task[3])
                            print(f'Modbus write: slave={task[1]}, reg={task[2]}, value={task[3]}, result={result}')
                        except Exception as e:
                            print(f'Ошибка записи: {e}')
                            self.connected  = False
                            self.host       = None
                            with self._lock:
                                self.queue.insert(0, task)
                
                time.sleep(0.1)  
                
            except Exception as e:
                print(f"Ошибка в работе: {e}")
                self.connected  = False
                self.host       = None
                time.sleep(1)
    
    def stop(self):
        self.running = False


try:
    modbus_client = ModbusClient()
    print("Модбас клиент создан")
except Exception as e:
    print(f"Не получилось создать модбас клиент: {e}")
    modbus_client = None


class Equipment(SFC):
    """ Базовый класс для работы с оборудованием: конвейера, механизмы"""
    IDLE        = 0
    STARTUP     = 1
    RUN         = 2
    STOP        = 3
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


    def __init__(self, id = None, parent = None, fault = None, 
                 q = None, lock = None, depends = None, start = None, 
                 stop = None, manual = None):
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
        return self.start if self.manual else self.on
        
    def set_stop(self):
        return self.stop if self.manual else self.off
        
    def _turnon(self):
        self.block  = False

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
        if power and not self._allowed():
            self.block  = True
            return
        self.q = power and not self.lock
        if power and self.lock:
            self.block  = True
        if not power:
            self.lock   = False

    def _begin(self):
        self.msg = f'{self.id} работа'

    def _end(self):
        self.msg = f'{self.id} завершено'
    
    def main(self):
        self.msg    = f'{self.id} начало работы'
        self.state  = Equipment.IDLE
        self.ready  = False
        self.busy   = False
        self.msg    = f'{self.id} oжидание старта'
        yield from self.until(lambda: self.q, step = "waiting start")

        self.msg    = f'{self.id} cтарт'

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
                self.msg = f'{self.id} аварийный останов после старта'
        else:
            self.ready = True
            self.state = Equipment.RUN
            self._begin()
            yield from self.till(lambda: self.q and self._allowed() and not self.lock, step = 'working')
            self._end()

        self._turnoff()
        self._ctl.unset()
        self.state      = Equipment.STOP
        self.busy       = False
        self.ready      = False
        if self.lock:
            self.msg    = f'{self.id} отключено -> заблокировано'
            self.block  = True

        self.q          = False
                
class EquipmentROT(Equipment):
    """Класс для управления оборудованием с датчиком вращения (конвейера, шнеки)"""
    rotating    = POU.var(False)
    rot         = POU.input(False, hidden = True)
    speed_p     = POU.var(100, persistent=True)
    speed_msg   = POU.var('Ожидание значения скорости')
    slave_addr  = POU.var(1) 
    
    def __init__(self, fault: bool = None, q: bool = None, lock: bool = None, rot: bool = None, 
                 depends: Equipment = None, id: str = None, parent: POU = None, start = None, 
                 stop = None, manual = None, slave_addr=1):
        super().__init__(fault=fault, q=q, lock=lock, depends=depends, id=id, parent=parent)
        self.rot            = rot
        self._rotating      = TOF(clk = TRIG(clk = lambda: self.rot), q = self.monitor)
        self.slave_addr     = slave_addr
        self._modbus_client = ModbusClient()
        self._last_mb_send  = 0
        self._prev_speed    = int(self.speed_p)
        self.set_speed(int(self.speed_p))
        self.subtasks       += (self._rotating, )

    def monitor(self, rot: bool):
        self.rotating = rot
        if not rot and self.q:
            self.ok = False
            self.msg = f'{self.id} ошибка: нет вращения'


    def set_speed(self, speed_percent: int):
        print(speed_percent)
        if 100 >= speed_percent >= 0:
            speed_value = int(1500 * speed_percent / 100)
            self.set_timeout(speed_value)
            self.speed_msg = f'Скорость {speed_value}: {speed_percent}%'
            
            self._modbus_client.write_register(
                self.slave_addr,
                2,
                speed_value
            )
            
            return True
        return False
    

    def set_timeout(self, speed_value):
        if      speed_value < 500:  self._rotating.pt = 35000
        elif    speed_value < 1000: self._rotating.pt = 25000
        elif    speed_value < 1500: self._rotating.pt = 15000
        else:                       self._rotating.pt = 35000
    
    def main(self):
        parent_main = super().main()
        
        while True:
            if self.speed_p != self._prev_speed:
                self.set_speed(self.speed_p)
                self._prev_speed = self.speed_p
            
            current_time = int(time.time() * 1000)
            if current_time - self._last_mb_send > 1000:
                self._modbus_client.write_register(
                    self.slave_addr,
                    2,
                    int(1500 * self.speed_p / 100)
                )
                self._last_mb_send = current_time
            
            try:
                next(parent_main)
            except StopIteration:
                break
                
            yield

class EquipmentFeeder(EquipmentROT):
    pult_start = POU.input(False)
    pult_stop  = POU.input(False)
    
    def __init__(self, pult_start=None, pult_stop=None, **kwargs):
        super().__init__(**kwargs)
        self.pult_start         = pult_start
        self.pult_stop          = pult_stop
        self._pult_start_trig   = RTRIG(clk=lambda: self.pult_start)
        self._pult_stop_trig    = RTRIG(clk=lambda: self.pult_stop)
        self.subtasks           += (self._pult_start_trig, self._pult_stop_trig)
    
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
    
    def __init__(self, gate=False, **kwargs):
        super().__init__(**kwargs)
        print(f'EquipmentPack {self.id}: gate bound to {gate}')

    
    def set_start(self):
        base_start = super().set_start()
        if self.manual: result = self.gate and base_start
        else: result = self.gate or base_start
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
        self._dummy         = TOF(clk=lambda: False, pt=1000)
        self.subtasks       += (self._dummy, )
    
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
        self.gears      = gears
        self._t_on      = FTRIG(clk = lambda: self.on )
        self._t_off     = RTRIG(clk = lambda: self.off )
        self._t_emerg   = FTRIG(clk=lambda: self.emerg)
        self.subtasks   = (self._t_on, self._t_off, self._t_emerg)
        self.state      = EquipmentChain.IDLE

    def _countdown(self, gear, action, total_time, condition):
        remaining = total_time
        if not condition: return
        while remaining >= 0:
            self.msg = f'{action} {gear.id}: {remaining} сек' # </bold>
            yield from self.pause(1000)
            remaining -= 1
        self.msg = f'Оборудование {gear.id} готово, переход к следующему..'
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