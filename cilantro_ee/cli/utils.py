import os
import sys
import psutil
import subprocess
import ipaddress
import cilantro_ee
import contracting
from checksumdir import dirhash
from contracting.client import ContractingClient
from cilantro_ee.storage.contract import BlockchainDriver


def validate_ip(address):
    try:
        ip = ipaddress.ip_address(address)
        print('%s is a correct IP%s address.' % (ip, ip.version))
        return ip
    except ValueError:
        print('address/netmask is invalid: %s' % address)


def build_pepper(pkg_dir_path= os.path.dirname(cilantro_ee.__file__)):

    if pkg_dir_path is None:
        # pkg_dir_path = '/Volumes/dev/lamden/cilantro-enterprise'
        pkg_dir_path = '../../cilantro_ee'

    pepper = dirhash(pkg_dir_path, 'sha256', excluded_extensions = ['pyc'])
    print(pepper)
    return pepper


def verify_cil_pkg(pkg_hash):
    current_pepper = build_pepper(pkg_dir_path = os.path.dirname(cilantro_ee.__file__))

    if current_pepper == pkg_hash:
        return True
    else:
        return False


def run(*args):
    return subprocess.check_call(['git'] + list(args))

def run_install(only_contaract=False):
    if not only_contaract:
        path =  os.path.join(os.path.dirname(cilantro_ee.__file__),  '..')
        os.chdir(f'{path}')
        subprocess.check_call(['python3', "setup.py", "develop"])  # "install"

    path2 =  os.path.join(os.path.dirname(contracting.__file__),  '..')
    os.chdir(f'{path2}')
    return subprocess.check_call(['python3', "setup.py", "develop"])  # "install"


def get_version(path = os.path.join( os.path.dirname(cilantro_ee.__file__), '..')):
    cur_branch_name = None
    try:
        os.chdir(path)
        cur_branch_name = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).rstrip().decode()
    except OSError as err:
        print("OS error: {0}".format(err))
    except:
        print("Unexpected error:", sys.exc_info())
    return cur_branch_name

def version_reboot(new_branch_name, new_contract_name='dev', contract_only=False):
    try:
        if not contract_only:
            path = os.path.join( os.path.dirname(cilantro_ee.__file__), '..')
            os.chdir(path)

            rel = new_branch_name  # input("Enter New Release branch:")
            br = f'{rel}'
            run("fetch", "--all")
            run("reset", "--hard", f"origin/{br}")

        path2 =  os.path.join(os.path.dirname(contracting.__file__), '..')
        os.chdir(path2)
        run("fetch", "--all")
        run("reset", "--hard", f"origin/{new_contract_name}")

    except OSError as err:
        print("OS error: {0}".format(err))
        return False
    except:
        print("Unexpected error:", sys.exc_info())
        return False

    return True


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
