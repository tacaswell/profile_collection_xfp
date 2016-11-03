def invivo_dr(flow_rate, pre_vol, exp_vol):
    '''Run dose-response experiment

    Parameters
    ----------
    flow_rate : float
        Flow rate in mL/min

    pre_vol : float
        volume to collect without exposure in mL

    exp_vol : float
        volume to collect with exposure in mL
    '''
    flow_rate_ulps = (flow_rate / 60) * 1000

    pre_exp_time = (pre_vol / flow_rate) *60
    exp_time = (exp_vol / flow_rate) *60
    dets = [shutter, sample_pump]
    # TODO add monitor on shutter status instead of TaR
    # TODO add monitor for pumps?
    # TODO add monitoring for fraction collector

    @bp.run_decorator(md={'plan_name': 'in_vivo'})
    def inner_plan():
        # prevent pausing
        yield from bp.clear_checkpoint()
        print("=== flowing at {} mL/m ({:.2f} uL/s)".format(flow_rate, flow_rate_ulps))
        yield from bp.abs_set(sample_pump.vel, flow_rate_ulps, wait=True)

        yield from bp.trigger_and_read(dets)

        # flow some sample through
        yield from bp.kickoff(sample_pump, wait=True)
        print("== started the flow pump")
        yield from bp.trigger_and_read(dets)

        print("== flowing pre-exposure sample for {}mL ({:.1f}s)".format(pre_vol, pre_exp_time))
        yield from bp.sleep(pre_exp_time)
        print("== Done flowing pre-exposure sample")
        #open the shutter
        yield from bp.abs_set(shutter, 'Open', wait=True)
        print("== Shutter open")
        yield from bp.trigger_and_read(dets)

        print("== flowing exposure sample for {}ml ({:.1f}s)".format(exp_vol, exp_time))
        # collect some sample with beam
        yield from bp.sleep(exp_time)

        # close the shutter and stop flowing the sample
        yield from bp.abs_set(shutter, 'Close', wait=True)
        yield from bp.complete(sample_pump, wait=True)

        print("done!")

        yield from bp.trigger_and_read(dets)

    def clean_up():
        yield from bp.abs_set(shutter, 'Close', wait=True)
        yield from bp.complete(sample_pump, wait=True)

    yield from bp.finalize_wrapper(inner_plan(), clean_up())
