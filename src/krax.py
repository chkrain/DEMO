from pyplc.platform import plc
from pyplc.utils.misc import TOF,TON
from equipment import EquipmentROT, Equipment, EquipmentChain, EquipmentDrum, EquipmentPack, EquipmentAutoStart, EquipmentROTAutoStart, EquipmentFeeder, Burner, Analog
from sys import platform
from collections import namedtuple

# m20 = EquipmentPack(q = plc.M20_ISON, rot = plc.M20_BELT, fault = plc.M20_ROPE, start = plc.M20_START, 
#                         stop = plc.M20_STOP, manual = plc.M20_MAN, depends = None, lock = plc.EMERGENCY, gate=plc.PACK2, slave_addr=7)

m20 = EquipmentROT(q = plc.M20_ISON, rot = plc.M20_BELT, fault = plc.M20_ROPE, start = plc.M20_START, 
                        stop = plc.M20_STOP, manual = plc.M20_MAN, depends = None, lock = plc.EMERGENCY, slave_addr=7)

m19 = EquipmentROT(q = plc.M19_ISON, rot = plc.M19_BELT, fault = plc.M19_ROPE, start = plc.M19_START, 
                        stop = plc.M19_STOP, manual = plc.M19_MAN, depends = None, lock = plc.EMERGENCY, slave_addr=13)

m18 = EquipmentROT(q = plc.M18_ISON, rot = plc.M18_BELT, fault = plc.M18_ROPE, start = plc.M18_START, 
                        stop = plc.M18_STOP, manual = plc.M18_MAN, depends = None, lock = plc.EMERGENCY, slave_addr=12)

m17 = Equipment(q = plc.M17_ISON, depends=m18, start = plc.M17_START, stop = plc.M17_STOP, manual = plc.M17_MAN, fault=plc.EMERGENCY, lock=None)

m16 = EquipmentROT(q = plc.M16_ISON, rot = plc.M16_BELT, fault = plc.M16_ROPE, start = plc.M16_START, 
                        stop = plc.M16_STOP, manual = plc.M16_MAN, depends = m17, lock = plc.EMERGENCY, slave_addr=6)

m15 = Equipment(q = plc.M15_ISON, depends=m16, start = plc.M15_START, stop = plc.M15_STOP, manual = plc.M15_MAN, fault=plc.EMERGENCY, lock=None)

m14 = EquipmentROT(q = plc.M14_ISON, rot = plc.M14_BELT, fault = plc.M14_ROPE, start = plc.M14_START, 
                        stop = plc.M14_STOP, manual = plc.M14_MAN, depends = m15, lock = plc.EMERGENCY, slave_addr=5)

m13 = EquipmentAutoStart(q = plc.M13_ISON, depends=None, start = plc.M13_START, stop = plc.M13_STOP, manual = plc.M13_MAN, auto_start_on=None, fault=plc.EMERGENCY)

m12 = EquipmentROTAutoStart(q = plc.M12_ISON, rot = True, fault = None, start = plc.M12_START, slave_addr=4,
                        stop = plc.M12_STOP, manual = plc.M12_MAN, depends = None, lock = None, auto_start_on=None)

# burner = Burner(depends=(m12, ))

m11 = EquipmentDrum(start=plc.M11_ESTART, stop=plc.M11_ESTOP, fault=plc.EMERGENCY, q=plc.M11_ISON)

m10 = EquipmentROT(q = plc.M10_ISON, rot = plc.M10_BELT, fault = plc.M10_ROPE, start = plc.M10_START, 
                        stop = plc.M10_STOP, manual = plc.M10_MAN, depends = m11, lock = plc.EMERGENCY, slave_addr=3)

m8 = EquipmentROT(q = plc.M8_ISON, rot = plc.M8_BELT, fault = plc.M8_ROPE, start = plc.M8_START,
                        stop = plc.M8_STOP, manual = plc.M8_MAN, depends = None, lock = plc.EMERGENCY, slave_addr=11)

m7 = EquipmentROT(q = plc.M7_ISON, rot = plc.M7_BELT, fault = plc.M7_ROPE, start = plc.M7_START, 
                        stop = plc.M7_STOP, manual = plc.M7_MAN, depends = m8, lock = plc.EMERGENCY, slave_addr=10)

m6 = Equipment(q = plc.M6_ISON, depends=m10, start = plc.M6_START, stop = plc.M6_STOP, manual = plc.M6_MAN, fault=plc.EMERGENCY, lock=None)

m5 = EquipmentROT(q = plc.M5_ISON, rot = plc.M5_BELT, fault = plc.M5_ROPE, start = plc.M5_START, 
                        stop = plc.M5_STOP, manual = plc.M5_MAN, depends = m6, lock = plc.EMERGENCY, slave_addr=9)

m4 = Equipment(q = plc.M4_ISON, depends=m5, start = plc.M4_START, stop = plc.M4_STOP, manual = plc.M4_MAN, fault=plc.EMERGENCY, lock=None)

m3 = EquipmentROT(q = plc.M3_ISON, rot = plc.M3_BELT, fault = plc.M3_ROPE, start = plc.M3_START, 
                        stop = plc.M3_STOP, manual = plc.M3_MAN, depends = m4, lock = plc.EMERGENCY, slave_addr=2)

m2 = Equipment(q = plc.M2_ISON, depends=m3, start = plc.M2_START, stop = plc.M2_STOP, manual = plc.M2_MAN, fault=plc.EMERGENCY, lock=None)

m1 = EquipmentFeeder(q = plc.M1_ISON, rot = plc.M1_BELT, fault = plc.M1_ROPE, start = plc.M1_START, 
                        stop = plc.M1_STOP, manual = plc.M1_MAN, depends = m2, lock = plc.EMERGENCY, pult_start=plc.M1_ESTART, 
                        pult_stop=plc.M1_ESTOP, slave_addr=1) 

compressor = EquipmentAutoStart(q = plc.COMPRES_ISON, depends=None, start = plc.COMPRES_START, fault=plc.EMERGENCY,
                                stop = plc.COMPRES_STOP, manual = plc.COMPRES_MAN, auto_start_on=(m18, m20))

m12.auto_start_on = (m11, m10, m1)
m13.auto_start_on = (m11, m14)

# temp_enter = Analog(raw_value=plc.TEMP_ENTER, threshold=10)

# temp_exit = Analog(raw_value=plc.TEMP_EXIT, threshold=10)

# humidity = Analog(raw_value=plc.HUMIDITY_EXIT, threshold=10)

# set_temp = Analog(raw_value=plc.TEMP_BURNER, threshold=5)

cascade = EquipmentChain( gears=(m19, m18, m17, m16, m15, m13, m14, m11, m10, m6, m5, m4, m3, m2, m1))

instances =  (m1, m2, m3, m4, m5, m6, m7, m8, m10, m11, m12, m13, m14, m15, m16, m17, m18, m19, m20, cascade, compressor ) 

try:
    from equipment import telegram_monitor

    if telegram_monitor:
        instances += (telegram_monitor,)
except Exception as e:
    print(f'Не удалось запустить бота: {e}')

if platform == 'linux':
    from imitation import IRotation, IForce

    force = IForce()

    irot1 = IRotation(q = plc.M1_ISON, rot = plc.M1_BELT)
    irot2 = IRotation(q = plc.M3_ISON, rot = plc.M3_BELT)
    irot3 = IRotation(q = plc.M5_ISON, rot = plc.M5_BELT)
    irot4 = IRotation(q = plc.M7_ISON, rot = plc.M7_BELT)
    irot5 = IRotation(q = plc.M8_ISON, rot = plc.M8_BELT)
    irot6 = IRotation(q = plc.M10_ISON, rot = plc.M10_BELT)
    irot7 = IRotation(q = plc.M14_ISON, rot = plc.M14_BELT)
    irot8 = IRotation(q = plc.M16_ISON, rot = plc.M16_BELT)
    irot9 = IRotation(q = plc.M18_ISON, rot = plc.M18_BELT)
    irot10 = IRotation(q = plc.M19_ISON, rot = plc.M19_BELT)
    irot11 = IRotation(q = plc.M20_ISON, rot = plc.M20_BELT)

    
    instances += (irot1, irot2,irot3,irot4,irot5,irot6,irot7,irot8,irot9,irot10,irot11, force)

plc.run(instances=instances, ctx=globals()) 