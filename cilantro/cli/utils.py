import os
import sys
import psutil
import subprocess
import ipaddress
import cilantro
from checksumdir import dirhash
from contracting.client import ContractingClient
from cilantro.storage.contract import BlockchainDriver


def validate_ip(address):
    try:
        ip = ipaddress.ip_address(address)
        print('%s is a correct IP%s address.' % (ip, ip.version))
        return ip
    except ValueError:
        print('address/netmask is invalid: %s' % address)


def build_pepper(pkg_dir_path=os.environ.get('CIL_PATH')):

    if pkg_dir_path is None:
        pkg_dir_path = '/Volumes/dev/lamden/cilantro-enterprise'

    pepper = dirhash(pkg_dir_path, 'sha256', excluded_extensions = ['pyc'])
    print(pepper)
    return pepper


def verify_cil_pkg(pkg_hash):
    current_pepper = build_pepper(pkg_dir_path = os.environ.get('CIL_PATH'))

    if current_pepper == pkg_hash:
        return True
    else:
        return False


def run(*args):
    return subprocess.check_call(['git'] + list(args))


def version_reboot():

    try:
        path = os.environ.get('CIL_PATH')
        os.chdir(path)

        # get latest release
        rel = input("Enter New Release branch:")
        br = f'{rel}'

        run("checkout", "-b", br)
    except OSError as err:
        print("OS error: {0}".format(err))
    except:
        print("Unexpected error:", sys.exc_info())
        raise

    # Find cil process
    PNAME = 'cil'
    for proc in psutil.process_iter():
        # check whether the process name matches
        if proc.name() == PNAME:
            proc.kill()




def get_update_state():
    driver = BlockchainDriver()
    active_upgrade = driver.get_var(contract='upgrade', variable='upg_lock', mark=False)
    pepper = driver.get_var(contract='upgrade', variable='upg_pepper', mark=False)
    start_time = driver.get_var(contract='upgrade', variable='upg_init_time', mark=False)
    window = driver.get_var(contract='upgrade', variable='upg_window', mark=False)
    mcount = driver.get_var(contract='upgrade', variable='tot_mn', mark=False)
    dcount = driver.get_var(contract='upgrade', variable='tot_dl', mark=False)
    mvotes = driver.get_var(contract='upgrade', variable='mn_vote', mark=False)
    dvotes = driver.get_var(contract='upgrade', variable='dl_vote', mark=False)
    consensus = driver.get_var(contract='upgrade', variable='upg_consensus', mark=False)

    print("Upgrade: {} Cil Pepper:  {}\n"
          "Init time:   {}, Time Window:    {}\n"
          "Masters:     {}\n"
          "Delegates:   {}\n"
          "MN-Votes:    {}\n "
          "DL-Votes:    {}\n "
          "Consensus:   {}\n"
          .format(active_upgrade, pepper, start_time, window, mcount, dcount,
                  mvotes, dvotes, consensus))
