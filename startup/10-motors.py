from ophyd import EpicsMotor, Device, Component as Cpt


class Slits(Device):
    top = Cpt(EpicsMotor, 'T}Mtr')
    bottom = Cpt(EpicsMotor, 'B}Mtr')
    inboard = Cpt(EpicsMotor, 'I}Mtr')
    outboard = Cpt(EpicsMotor, 'O}Mtr')


class InBottomSlits(Device):
    bottom = Cpt(EpicsMotor, 'B}Mtr')
    inboard = Cpt(EpicsMotor, 'I}Mtr')


class TopOutSlits(Device):
    top = Cpt(EpicsMotor, 'T}Mtr')
    outboard = Cpt(EpicsMotor, 'O}Mtr')


pbslits = Slits('XF:17BMA-OP{Slt:PB-Ax:', name='pbslits')
feslits1 = TopOutSlits('FE:C17B-OP{Slt:1-Ax:', name='feslits1')
feslits2 = InBottomSlits('FE:C17B-OP{Slt:2-Ax:', name='feslits2')
