from subprocess import Popen, PIPE
import os
import sys
import time


def main(argv):

    rc = 1
    while rc is not 0:

        if len(argv) == 0:
            print("Usage: python restart.py [python file]")
            return

        file = os.path.abspath(argv[0])

        cmd = ['python', file]

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
    # Must run restart.py while in the same directory as restart.py
    # Usage: python restart.py [python file]

    main(sys.argv[1:])