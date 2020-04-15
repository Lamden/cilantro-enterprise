import json
import os, signal
import psutil
import time
from cilantro_ee.cli.utils import restart
from cilantro_ee.cli.start import start_mongo

def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        #signal 0 just checks for pid status
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def find_pid(name):
    try:
        PNAME = name
        for proc in psutil.process_iter():
            # check whether the process name matches
            if proc.name() == PNAME:
                return proc.pid
    except BaseException as err:
        print("Node Setup not finished")
        print("Error: {}".format(err))
        return -1


def main():

    mpid = find_pid(name='mongod')
    cpid = find_pid(name='cil')

    if -1 in {mpid, cpid}:
        return

    while (True):
        time.sleep(10)
        m_status = check_pid(mpid)
        c_status = check_pid(cpid)

        if False in {c_status, m_status}:
            try:
                os.kill(mpid, signal.SIGTERM)
                os.kill(cpid, signal.SIGTERM)
            except BaseException as err:
                print("Error: {}".format(err))
                continue

            # start mongo
            start_mongo()

            # restart node from config
            restart()


if __name__ == "__main__":
    # execute only if run as a script
    main()