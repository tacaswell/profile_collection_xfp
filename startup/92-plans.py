#Capillary destructive testing

import datetime

def timed_shutter(exp_time, *, md=None):

    dets = [shutter]

    if md is None:
        md = {}

    md['exp_time'] = exp_time

    @bp.run_decorator(md={'plan_name': 'timed_shutter'})
    def inner_plan():
        yield from bp.clear_checkpoint()
        
        # open the shutter
        yield from bp.abs_set(shutter, 'Open', wait=True)
        yield from bp.trigger_and_read(dets)

        print('Shutter opened')
        print("({}) Exposing for {:.2f} s".format(datetime.datetime.now().strftime(_time_fmtstr), exp_time))

       # wait
        yield from bp.sleep(exp_time)

       # close the shutter
        yield from bp.abs_set(shutter, 'Close', wait=True)
        print('closed shutter')
        yield from bp.trigger_and_read(dets)

    def clean_up():
        yield from bp.abs_set(shutter, 'Close', wait=True)


    yield from bp.finalize_wrapper(inner_plan(), clean_up())

