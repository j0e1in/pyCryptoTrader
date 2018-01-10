from pprint import pprint
from subprocess import Popen, PIPE
import sys


cmds = [
    ["python", "analysis/hist_data_test.py"],
    ["python", "db_test.py"],
    ["python", "analysis/backtest_trader_test.py"],
    ["python", "analysis/backtest_test.py"],
    ["python", "analysis/plot_test.py"],
    ["python", "analysis/strategy_test.py"]
]


def main(argv):

    starting_test = int(argv[0]) if len(argv) > 0 else 0

    for i, cmd in enumerate(cmds):

        if i >= starting_test - 1:
            cmd_msg = ' '.join(cmd)
            print(f"\n>>>>>>>>>> RUNNING {cmd_msg} <<<<<<<<<<\n")
            p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)

            output, err = p.communicate()
            rc = p.returncode
            if rc is not 0:
                err = err.decode('utf-8')
                print("Error Message:\n")
                print(err)
                sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])