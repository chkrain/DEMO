from umodbus.tcp import TCP as ModbusTCPMaster
import time

class ModbusManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.slave_tcp_port = 502
        self.slave_ip = '192.168.8.15'
        self.host = None
        self.last_connection_attempt = 0
        self.connection_timeout = 5  
        self._connect()
    
    def _connect(self):
        """Установка соединения с Modbus устройством"""
        current_time = time.time()
        if current_time - self.last_connection_attempt < self.connection_timeout:
            return False
            
        self.last_connection_attempt = current_time
        
        try:
            self.host = ModbusTCPMaster(
                slave_ip=self.slave_ip,
                slave_port=self.slave_tcp_port,
                timeout=5.0  # Увеличиваем таймаут для стабильности
            )
            print("Modbus соединение установлено")
            return True
        except Exception as e:
            print(f"Ошибка подключения Modbus: {e}")
            self.host = None
            return False
    
    def write_register(self, slave_addr, register_address, register_value):
        """Безопасная запись регистра с обработкой ошибок"""
        if self.host is None:
            if not self._connect():
                print(f"Modbus устройство {slave_addr} недоступно")
                return False
        
        try:
            self.host.write_single_register(
                slave_addr=slave_addr,
                register_address=register_address,
                register_value=register_value
            )
            return True
        except OSError as e:
            if e.errno == 128:  # ENOTCONN
                print("Соединение разорвано, переподключение...")
                self.host = None
                if not self._connect():
                    print("Не удалось восстановить соединение с Modbus устройством")
                    return False
                # Повторяем попытку после переподключения
                try:
                    self.host.write_single_register(
                        slave_addr=slave_addr,
                        register_address=register_address,
                        register_value=register_value
                    )
                    return True
                except Exception as retry_e:
                    print(f"Ошибка при повторной попытке записи: {retry_e}")
                    return False
            else:
                print(f"OSError при записи регистра: {e}")
                self.host = None
                return False
        except Exception as e:
            print(f"Неожиданная ошибка при записи регистра: {e}")
            self.host = None
            return False

# Глобальный экземпляр менеджера
modbus_manager = ModbusManager()