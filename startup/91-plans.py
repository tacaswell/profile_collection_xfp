#NEEDS WORK - NOT FINISHED!!!!!

import datetime
_time_fmtstr = '%Y-%m-%d %H:%M:%S'

def tr_pump(mix_flow_rate, mix_vol, mixing_time, exp_flow_rate, exp_vol, *, md=None):
    '''Run time-resolved experiment

    Parameters
    ----------
    mix_flow_rate : float
        flow rate in mL/min for mixing

    mix_vol : float
        volume to push for mixing without exposure in mL

    mixing_time : float
        time in seconds for mixing prior to exposure

    exp_flow_rate : float
        flow rate in mL/min for exposure and collection

    exp_vol : float
        volume to collect with exposure in mL
    ''' 

    dets = [shutter, spump]

    # waiting times in seconds
    mixing_time = .05

    if md is None:
        md = {}

    md['mix_flow_rate'] = mix_flow_rate
    md['mix_vol'] = mix_vol
    md['mixing_time'] = mixing_time
    md['exp_flow_rate'] = exp_flow_rate
    md['exp_vol'] = exp_vol

    @bp.run_decorator(md=ChainMap(md, {'plan_name': 'tr_pump'}))
    def inner_plan():
        yield from bp.clear_checkpoint()
        
        # start the pump for mixing
        print('waiting for pump to start')
        yield from bp.kickoff(spump, wait=True)

        print("== ({}) flowing at {} mL/m".format(datetime.datetime.now().strftime(_time_fmtstr), mix_flow_rate))
        st = yield from bp.complete(spump, wait=False, group='pump complete')
        print('waiting for pump
 to finish')
        yield from bp.wait('pump complete')
        # open the shutter
        yield from bp.abs_set(shutter, 'Open', wait=True)
        yield from bp.trigger_and_read(dets)

        while st is not None and not st.done:
            yield from bp.trigger_and_read(spump)
            yield from bp.sleep(.5)

        yield from bp.sleep(.1)
        yield from bp.trigger_and_read(dets)

        yield from bp.wait('pump_done')
        print("({}) first push complete, mixing for {:.2f} s".format(datetime.datetime.now().strftime(_time_fmtstr), mixing_time))

        yield from bp.sleep(mixing_time)

        # start the pump for exposure and collection
        yield from bp.kickoff(spump, wait=True)

        yield from bp.wait('pump_started')
        print("== ({}) flowing at {} mL/m".format(datetime.datetime.now().strftime(_time_fmtstr), exp_flow_rate))
        st = yield from bp.complete(spump, group='pump_done', wait=False)
        print('waiting for pump to finish')

        yield from bp.abs_set(shutter, 'Close', wait=True)
        print('closed shutter')

    def clean_up():
        yield from bp.abs_set(shutter, 'Close', wait=True)


    yield from bp.finalize_wrapper(inner_plan(), clean_up())

