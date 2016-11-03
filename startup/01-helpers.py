

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
