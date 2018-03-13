from subprocess import Popen, PIPE

import argparse
import os
import sys
import time


def main():
    # Must run restart.py while in the same directory as the target script
    # Example: python restart.py start_trader.py --args=--log-signal

    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=str, help='Python script to run.')
    parser.add_argument('--args', type=str, default='', help='Arguments to pass to the target script.')
    argv = parser.parse_args()

    rc = 1
    while rc is not 0:

        file = os.path.abspath(argv.file)

        cmd = ['python', file]

        if argv.args:
            cmd += argv.args.split(' ')

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

        with open('restart.log', 'a') as f:
            f.write(msg)

        time.sleep(3)


if __name__ == '__main__':
    main()