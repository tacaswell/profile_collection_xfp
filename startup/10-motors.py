from ophyd import (EpicsMotor, Device,
                   Component as Cpt, EpicsSignal,
                   EpicsSignalRO, DeviceStatus)
import bluesky.plans as bp
import time
import datetime

class TwoButtonShutter(Device):
    # TODO this needs to be fixed in EPICS as these names make no sense
    # the vlaue comingout of the PV do not match what is shown in CSS
    open_cmd = Cpt(EpicsSignal, 'Cmd:Opn-Cmd', string=True)
    open_val = 'Open'

    close_cmd = Cpt(EpicsSignal, 'Cmd:Cls-Cmd', string=True)
    close_val = 'Not Open'

    status = Cpt(EpicsSignalRO, 'Pos-Sts', string=True)
    fail_to_close = Cpt(EpicsSignalRO, 'Sts:FailCls-Sts', string=True)
    fail_to_open = Cpt(EpicsSignalRO, 'Sts:FailOpn-Sts', string=True)
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

        def shutter_cb(value, timestamp, **kwargs):
            value = enums[int(value)]
            if value == target_val:
                self._set_st._finished()
                self._set_st = None
                self.status.clear_sub(shutter_cb)

        cmd_enums = cmd_sig.enum_strs
        count = 0
        def cmd_retry_cb(value, timestamp, **kwargs):
            nonlocal count
            value = cmd_enums[int(value)]
            # ts = datetime.datetime.fromtimestamp(timestamp).strftime(_time_fmtstr)
            # print('sh', ts, val, st)
            count += 1
            if count > 5:
                cmd_sig.clear_sub(cmd_retry_cb)
                st._finished(success=False)
            if value == 'None':
                if not st.done:
                    time.sleep(.5)
                    cmd_sig.set(1)
                    ts = datetime.datetime.fromtimestamp(timestamp).strftime(_time_fmtstr)
                    print('** ({}) Had to reactuate shutter while {}ing'.format(ts, val))
                else:
                    cmd_sig.clear_sub(cmd_retry_cb)
                    
        cmd_sig.subscribe(cmd_retry_cb, run=False)        
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
        # The timeout controls how long to wait for the pump
        # to report it started working before assuming it is broken
        st = DeviceStatus(self, timeout=1.5)
        enums = self.sts.enum_strs
        def inner_cb(value, old_value, **kwargs):

            old_value, value = enums[int(old_value)], enums[int(value)]
            # print('ko', old_value, value, time.time())
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
            # print('cp', kwargs['timestamp'], old_value, value, value == 'Stopped')
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
                         read_attrs=['vel', 'sts'])
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
spump = Pump('XF:17BM-ES:1{Pmp:01}', name='syringe_pump')

#pbslits = Slits('XF:17BMA-OP{Slt:PB-Ax:', name='pbslits')
#feslits1 = TopOutSlits('FE:C17B-OP{Slt:1-Ax:', name='feslits1')
#feslits2 = InBottomSlits('FE:C17B-OP{Slt:2-Ax:', name='feslits2')
