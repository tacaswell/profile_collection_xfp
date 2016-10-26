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
    ...

class FractionCollector(Device):
    ...

sample_pump = SamplePump('', name='sample_pump')
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

def pump_plan(volume, rate):
    yield from bp.abs_set(pump.volume, volume, group='pump')
    yield from bp.abs_set(pump.infusion_rate, rate, group='pump')
    yield from bp.wait(group='pump')
    yield from bp.sleep(15)

def run_the_pump(pmp, **kwargs):
    yield from bp.configure(pmp, kwargs)
    yield from bp.abs_set(shutter, 'open', wait=True)
    yield from bp.kickofff(pmp, group='pump_started')
    yield from bp.wait(group='pump_started')
    yield from bp.complete(pmp, group='pump_done')
    yield from bp.wait(group='pump_done')
    yield from bp.abs_set(shutter, 'close', wait=True)
    

def simple_pump(pump):
    
    @bp.run_decorator(md={'plan_name': 'simple_pump'})
    def inner_plan():
        yield from bp.clear_checkpoint()
        yield from bp.abs_set(shutter, 'Open', wait=True)

        yield from bp.kickoff(pump, group='pump_started')
        print('waiting for pump to start')
        
        yield from bp.wait('pump_started')
        print('pump started')
        st = yield from bp.complete(pump, group='pump_done', wait=False)
        print('waiting for pump to finish')
        
        yield from bp.trigger_and_read([pump])
              
        while st is not None and not st.done:
            yield from bp.trigger_and_read([pump])
            yield from bp.sleep(.5)
            
        yield from bp.sleep(.1)            
        yield from bp.trigger_and_read([pump])
        
        yield from bp.wait('pump_done')
        print('pump finished')
        
        yield from bp.abs_set(shutter, 'Close', wait=True)
        print('closed shutter')

    def clean_up():
        yield from bp.abs_set(shutter, 'Close', wait=True)
        
        
    yield from bp.finalize_wrapper(inner_plan(), clean_up())


def in_vivo(food_pump, sample_pump, fraction_collector, shutter):
    # waiting times in seconds
    pre_flow_time = 5
    exposure_time = 5
    growth_time = 5
    post_growth_exposure_time = 5
    dets = [shutter, sample_pump, fraction_collector]
    # TODO add monitor on shutter status instead of TaR
    # TODO add monitor for pumps?
    # TODO add monitoring for fraction collector
    @bp.run_decorator(md={'plan_name': 'in_vivo'})
    def inner_plan():
        # prevent pausing
        yield from bp.clear_checkpoint()

        #start the fraction collector spinning
        yield from bp.kickoff(fraction_collector)
        # flow some sample through
        yield from bp.kickoff(sample_pump, wait=True)
        yield from bp.trigger_and_read(dets)

        yield from bp.sleep(pre_flow_time)
        
        #open the shutter
        yield from bp.abs_set(shutter, 'Open', wait=True)
        yield from bp.trigger_and_read(dets)
        
        # collect some sample with beam
        yield from bp.sleep(exposure_time)
        
        # close the shutter and stop flowing the sample
        yield from bp.abs_set(shutter, 'Close', wait=True)
        yield from bp.complete(sample_pump, wait=True)
        yield from bp.complete(fraction_collector, wait=True)
        
        yield from bp.trigger_and_read(dets)
        
        # feed the cells
        yield from bp.kickoff(food_pump, wait=True)
        yield from bp.complete(food_pump, wait=True)

        # let them grow
        yield from bp.sleep(growth_time)

        #open the shutter
        yield from bp.abs_set(shutter, 'Open', wait=True)
        #start the fraction collector spinning and flow some sample through
        yield from bp.kickoff(fraction_collector, wait=True)
        yield from bp.kickoff(sample_pump, wait=True)
        yield from bp.trigger_and_read(dets)
        
        # collect some sample with beam
        yield from bp.sleep(post_growth_exposure_time)
        
        # close the shutter and stop flowing the sample
        yield from bp.abs_set(shutter, 'Close', wait=True)
        yield from bp.complete(sample_pump, wait=True)
        yield from bp.complete(fraction_collector, wait=True)
        
        yield from bp.trigger_and_read(dets)

    def clean_up():
        yield from bp.abs_set(shutter, 'Close', wait=True)
        yield from bp.complete(sample_pump, wait=True)
        yield from bp.complete(fraction_collector, wait=True)
        
    yield from bp.finalize_wrapper(inner_plan(), clean_up())

    
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
