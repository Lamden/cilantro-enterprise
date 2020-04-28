import os
import json
import shlex
import sys
from getpass import getpass

import psutil
import pathlib
import subprocess
import ipaddress
import cilantro_ee
from checksumdir import dirhash
from contracting.client import ContractingClient
from cilantro_ee.storage.contract import BlockchainDriver
from cilantro_ee.logger.base import get_logger
from cilantro_ee.crypto.wallet import Wallet


log = get_logger('Cmd')


def validate_ip(address):
    try:
        ip = ipaddress.ip_address(address)
        log.info('%s is a correct IP%s address.' % (ip, ip.version))
        return ip
    except ValueError:
        log.error('address/netmask is invalid: %s' % address)


def build_pepper(pkg_dir_path=os.environ.get('CIL_PATH')):

    if pkg_dir_path is None:
        pkg_dir_path = '/Volumes/dev/lamden/cilantro-enterprise'

    pepper = dirhash(pkg_dir_path, 'sha256', excluded_extensions = ['pyc'])
    return pepper


def verify_cil_pkg(pkg_hash):
    if pkg_hash is None:
        return False

    current_pepper = build_pepper(pkg_dir_path = os.environ.get('CIL_PATH'))

    if current_pepper == pkg_hash:
        return True
    else:
        return False


def strip_ip(node):
    return node[6:]


def ask(question):
    while "the answer is invalid":
        reply = str(input(question+' (y/n): ')).lower().strip()
        if reply[0] == 'y':
            print("Selected: {}".format(reply[0]))
            return True
        if reply[0] == 'n':
            print("Selected: {}".format(reply[0]))
            return False


def run(*args):
    return subprocess.check_call(['git'] + list(args))


def reboot_config(key=None):
    if key is None:
        return

    myid = {'sk': key}

    rel = input("Enter New Release branch:")
    myid['target'] = rel

    with open('key.json', 'w') as outfile:
        json.dump(myid, outfile)
    log.info("Writing config")


def read_cfg():
    # Read configs
    pkg_root = '/root/cilantro-enterprise'

    try:
        key_path = pkg_root + '/key.json'
        f = open(str(key_path), 'r')
        k = json.load(f)
        f.close()
    except IOError:
        log.error("Manual restart needed, couldn't read config")
        return None, None
    except BaseException as err:
        log.error("{}".format(err))
        return None, None

    assert 'sk' in k.keys(), 'No key found.'
    print(k)

    try:
        cfg_path = pkg_root + '/network_info.json'
        f = open(str(cfg_path), 'r')
        cfg = json.load(f)
        f.close()
    except IOError:
        log.error("Config not found - restart manually")
        return

    assert 'nodes' in cfg.keys(), 'No bootnodes found'
    assert 'version' in cfg.keys(), 'No pepper found'
    assert 'type' in cfg.keys(), 'No Node Type'
    print(cfg)

    return k, cfg


def checkout(target=None):
    try:
        path = '/root/cilantro-enterprise'
        os.chdir(path)

        # get latest release
        br = f'{target}'
        run("checkout", "-b", br)

    except OSError as err:
        log.error("OS error: {0}".format(err))
        return err
    except:
        log.error("Unexpected error: {}".format(sys.exc_info()))


def restart():
    k, cfg = read_cfg()

    if k is None or cfg is None:
        log.error("Failed to read config, manual restart needed")
    else:
        checkout(target=k['target'])

    bn = cfg['nodes']
    bn_str = ''

    for i in bn:
        bn_str = bn_str + " " + i

    cmd = f"cil start {cfg['type']} -k {k['sk']} -bn {bn_str}"
    print(cmd)

    args = shlex.split(cmd)

    print(args)
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Restarted proc {}".format(p.pid))
    stdout = p.stdout.read()
    stderr = p.stderr.read()
    if stdout:
        print(stdout.decode())
    if stderr:
        print(stderr.decode())


def version_reboot(bn, is_master):
    driver = BlockchainDriver()
    active_upgrade = driver.get_var(contract='upgrade', variable='upg_lock', mark=False)

    if active_upgrade is True:
        target_version = driver.get_var(contract='upgrade', variable='upg_pepper', mark=False)
    else:
        target_version = None
        assert target_version is None, "New version target Cannot be None"
        return

    info = {}
    info['nodes'] = [strip_ip(i) for i in bn]
    info['version'] = target_version

    if is_master:
        info['type'] = 'masternode'
    else:
        info['type'] = 'delegate'

    with open('network_info.json', 'w') as outfile:
        json.dump(info, outfile)

    # Find cil process
    PNAME = 'cil'
    for proc in psutil.process_iter():
        # check whether the process name matches
        if proc.name() == PNAME:
            print("{} : {} proc shutting down".format(proc.pid, proc.name()))
            proc.kill()
            #restart()


def get_update_state():
    driver = BlockchainDriver()
    active_upgrade = driver.get_var(contract='upgrade', variable='upg_lock', mark=False)
    pepper = driver.get_var(contract='upgrade', variable='upg_pepper', mark=False)
    start_time = driver.get_var(contract='upgrade', variable='S', arguments=['init_time'], mark=False)
    current_time = driver.get_var(contract='upgrade', variable='S', arguments=['today'], mark=False)
    window = driver.get_var(contract='upgrade', variable='S', arguments=['window'], mark=False)
    mcount = driver.get_var(contract='upgrade', variable='tot_mn', mark=False)
    dcount = driver.get_var(contract='upgrade', variable='tot_dl', mark=False)
    mvotes = driver.get_var(contract='upgrade', variable='mn_vote', mark=False)
    dvotes = driver.get_var(contract='upgrade', variable='dl_vote', mark=False)
    consensus = driver.get_var(contract='upgrade', variable='upg_consensus', mark=False)

    print("Upgrade: {} Cil Pepper:  {}\n"
          "Init time:   {}, Last_Check: {}, Time Window: {}\n"
          "Masters:     {}\n"
          "Delegates:   {}\n"
          "MN-Votes:    {}\n "
          "DL-Votes:    {}\n "
          "Consensus:   {}\n"
          .format(active_upgrade, pepper, start_time, current_time, window, mcount, dcount,
                  mvotes, dvotes, consensus))


def validate_key(restart=False, key=None):
    while True:
        if key is None:
            sk = getpass('Signing Key in Hex Format: ')
        else:
            sk = key

        try:
            wallet = Wallet(seed=bytes.fromhex(sk))
            print('Access validated')
            if restart is True:
                reboot_config(key=sk)
            return wallet
        except:
            print('Invalid format! Try again.')