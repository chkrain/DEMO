from pyplc.platform import plc
from pyplc.pou import POU
from pyplc.utils.latch import RS
from pyplc.sfc import SFC


# self.conveyor_to_screen2_logic = RS(
#     set=lambda: self.station13_start,
#     reset=lambda: self.station13_stop,
#     q = lambda x: setattr('conveyor6508000_screen_on', x)
# )

def func():
    plc.DO_CONVEYOR6506000_PACKING_TURNON = True
    yield
    plc.DO_CONVEYOR6506000_PACKING_TURNON = False
    yield
    plc.DO_CONVEYOR6501000_DRUM_TURNON = True
    yield
    plc.DO_CONVEYOR6501000_DRUM_TURNON = False
    yield


if __name__ == "__main__":
    plc.run(instances=[func], ctx=globals())