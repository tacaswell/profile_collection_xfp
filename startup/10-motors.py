from ophyd import (EpicsMotor, Device,
                   Component as Cpt, EpicsSignal,
                   EpicsSignalRO, StatusBase)
import bluesky.plans as bp


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
        st = StatusBase()
        enums = self.state.enum_strs
        if self._kickoff_st is not None:
            raise RuntimeError('trying to kickoff before previous kickoff done')
        self._kickoff_st = st = StatusBase()
        def inner_cb(value, old_value, **kwargs):
            old_value, value = enums[int(old_value)], enums[int(value)]
                     
            if value == 'Interrupted':
                st._finished(success=False)
                self.state.clear_sub(inner_cb)
                     
            if old_value == 'Idle' and value != 'Idle':
                st._finished(success=True)
                self.state.clear_sub(inner_cb)

        self.state.subscribe(inner_cb, run=False)
        
        self.run.set('Run')
        return st

    def complete(self):
        st = StatusBase()
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

    
pump = Pump('XF:17BM-ES:1{Pmp:01}', name='pump')

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
    

def simple_pump():
    
    @bp.run_decorator(md={'plan_name': 'simple_pump'})
    def inner_plan():
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

    yield from inner_plan()
