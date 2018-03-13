from subprocess import Popen, PIPE

import argparse
import os
import sys
import time


def main():
    # Must run restart.py while in the same directory as the target script
    # Example: python restart.py start_trader.py --args=--log-signal

    rc = 1
    while rc is not 0:

        file_dir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.abspath(f"{file_dir}/start_trader.py")

        cmd = ['python', file]

        if sys.argv[-1] != 'None':
            cmd += sys.argv[1:]

        p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)

        print("----------- Process started ----------")

        for line in p.stdout:
            sys.stdout.write(line.decode('utf-8'))

        output, err = p.communicate()
        rc = p.returncode

        if rc is 0: # success
            output = output.decode('utf-8')
            msg = f"[Output Message]\n{output}"

        else: # failure
            err = err.decode('utf-8')
            msg = f"[Error Message]\n{err}"

            print("----------- Restarting Process ----------")

        print(msg)

        with open('log/restart.log', 'a') as f:
            f.write(msg)

        time.sleep(3)


if __name__ == '__main__':
    main()