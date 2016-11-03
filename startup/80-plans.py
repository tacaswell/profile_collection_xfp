
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
