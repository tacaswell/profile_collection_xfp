from ophyd import (EpicsMotor, Device,
                   Component as Cpt, EpicsSignal,
                   EpicsSignalRO, DeviceStatus)
import bluesky.plans as bp


class TwoButtonShutter(Device):
    # TODO this needs to be fixed in EPICS as these names make no sense
    # the vlaue comingout of the PV do not match what is shown in CSS
    open_cmd = Cpt(EpicsSignal, 'Cmd:In-Cmd')
    open_val = 'Inserted'

    close_cmd = Cpt(EpicsSignal, 'Cmd:Out-Cmd')
    close_val = 'Not Inserted'

    status = Cpt(EpicsSignalRO, 'Pos-Sts', string=True)

    # user facing commands
    open_str = 'Open'
    close_str = 'Close'

    def set(self, val):
        if self._set_st is not None:
            raise RuntimeError('trying to set while a set is in progress')

        cmd_map = {self.open_str: self.open_cmd,
                   self.close_str: self.close_cmd}
        target_map = {self.open_str: self.open_val,
                      self.close_str: self.close_val}

        cmd_sig = cmd_map[val]
        target_val = target_map[val]

        st = self._set_st = DeviceStatus(self)
        enums = self.status.enum_strs

        def shutter_cb(value, **kwargs):
            value = enums[int(value)]
            if value == target_val:
                self._set_st._finished()
                self._set_st = None
                self.satus.clear_cb(shutter_cb)

        cmd_sig.set(1)
        self.status.subscribe(shutter_cb)

        return st

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_st = None
        self.read_attrs = ['status']

shutter = TwoButtonShutter('XF:17BMA-EPS{Sh:1}', name='shutter')

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



class SamplePump(Device):
    vel = Cpt(EpicsSignal, 'Val:Vel-SP')
    vol = Cpt(EpicsSignal, 'Val:Vol-SP')

    sts = Cpt(EpicsSignal, 'Sts:Flag-Sts')

    slew_cmd = Cpt(EpicsSignal, 'Cmd:Slew-Cmd')
    stop_cmd = Cpt(EpicsSignal, 'Cmd:Stop-Cmd')
    movr_cmd = Cpt(EpicsSignal, 'Cmd:MOVR-Cmd')

    sts = Cpt(EpicsSignal, 'Sts:Flag-Sts', string=True)

    def kickoff(self):
        st = DeviceStatus(self)
        enums = self.sts.enum_strs
        def inner_cb(value, old_value, **kwargs):
            old_value, value = enums[int(old_value)], enums[int(value)]

            if value == 'Moving':
                st._finished(success=True)
                self.sts.clear_sub(inner_cb)

        self.sts.subscribe(inner_cb)
        self.slew_cmd.put(1)
        return st

    def complete(self):
        st = DeviceStatus(self)
        enums = self.sts.enum_strs
        def inner_cb(value, old_value, **kwargs):
            old_value, value = enums[int(old_value)], enums[int(value)]

            if value == 'Stopped':
                st._finished(success=True)
                self.sts.clear_sub(inner_cb)

        self.sts.subscribe(inner_cb)

        self.stop_cmd.put(1)
        return st

    def stop(self):
        self.stop_cmd.put(1)

class FractionCollector(Device):
    ...

sample_pump = SamplePump('XF:17BMA-ES:1{Pmp:02}',
                         name='sample_pump',
                         read_attrs=['vel', 'vol', 'sts'])
fraction_collector = SamplePump('', name='fraction_collector')

class Pump(Device):
    # This needs to be turned into a PV positioner
    mode = Cpt(EpicsSignal, 'Mode', string=True)
    direction = Cpt(EpicsSignal, 'Direction', string=True)

    diameter = Cpt(EpicsSignal, 'Diameter_RBV', write_pv='Diameter')
    infusion_rate = Cpt(EpicsSignal, 'InfusionRate_RBV', write_pv='InfusionRate')
    run = Cpt(EpicsSignal, 'Run', string=True)
    state = Cpt(EpicsSignalRO, 'State_RBV', string=True)
    infusion_volume = Cpt(EpicsSignal, 'InfusionVolume_RBV', write_pv='InfusionVolume')

    delivered = Cpt(EpicsSignalRO, 'Delivered_RBV')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._kickoff_st = None
        self._complete_st = None
        self.read_attrs = ['delivered']
        self.configuration_attrs = ['diameter', 'infusion_rate', 'infusion_volume']

    def kickoff(self):
        enums = self.state.enum_strs
        if self._kickoff_st is not None:
            raise RuntimeError('trying to kickoff before previous kickoff done')
        self._kickoff_st = st = DeviceStatus(self)
        def inner_cb(value, old_value, **kwargs):
            old_value, value = enums[int(old_value)], enums[int(value)]

            if value == 'Interrupted':
                st._finished(success=False)
                self.state.clear_sub(inner_cb)

            if value in {'Infusing', 'Withdrawing'}:
                st._finished(success=True)
                self.state.clear_sub(inner_cb)

        self.state.subscribe(inner_cb, run=False)

        self.run.set('Run')
        return st

    def complete(self):
        st = DeviceStatus(self)
        enums = self.state.enum_strs
        if self._kickoff_st is None:
            raise RuntimeError('must kickoff before completing')
        if self._complete_st is not None:
            raise RuntimeError('trying to complete before previous complete done')

        def inner_cb(value, old_value, **kwargs):
            old_value, value = enums[int(old_value)], enums[int(value)]

            if value == 'Idle' and old_value != 'Idle':
                st._finished(success=True)
                self.state.clear_sub(inner_cb)
                self._kickoff_st = None
                self._complete_st = None

            if value == 'Interrupted':
                st._finished(success=False)
                self.state.clear_sub(inner_cb)
                self._kickoff_st = None
                self._complete_st = None

        self.state.subscribe(inner_cb, run=self._kickoff_st.done)
        return st

    def stop(self, success=False):
        if self._kickoff_st is not None:
            self._kickoff_st._finished(success=success)

        if self._complete_st is not None:
            self._complete_st._finished(success=success)

        self._complete_st = None
        self._kickoff_st = None
        self.run.set('Stop')

pump1 = Pump('XF:17BM-ES:1{Pmp:01}', name='food_pump')

#pbslits = Slits('XF:17BMA-OP{Slt:PB-Ax:', name='pbslits')
#feslits1 = TopOutSlits('FE:C17B-OP{Slt:1-Ax:', name='feslits1')
#feslits2 = InBottomSlits('FE:C17B-OP{Slt:2-Ax:', name='feslits2')


def print_summary(plan):
    """Print summary of plan

    Prints a minimal version of the plan, showing only moves and
    where events are created.

    Parameters
    ----------
    plan : iterable
        Must yield `Msg` objects
    """

    read_cache = []
    for msg in plan:
        cmd = msg.command
        if cmd == 'open_run':
            print('{:=^80}'.format(' Open Run '))
        elif cmd == 'close_run':
            print('{:=^80}'.format(' Close Run '))
        elif cmd == 'set':
            print('{motor.name} -> {args[0]}'.format(motor=msg.obj,
                                                     args=msg.args))
        elif cmd == 'create':
            pass
        elif cmd == 'read':
            read_cache.append(msg.obj.name)
        elif cmd == 'save':
            print('  Read {}'.format(read_cache))
            read_cache = []
        elif cmd == 'kickoff':
            print('start: {flyer.name}'.format(flyer=msg.obj))
        elif cmd == 'complete':
            print('wait for/stop: {flyer.name}'.format(flyer=msg.obj))
        elif cmd == 'sleep':
            print('***** wait for {}s'.format(msg.args[0]))
