import os
import json
import sys
import psutil
import pathlib
import subprocess
import ipaddress
import cilantro_ee
from checksumdir import dirhash
from contracting.client import ContractingClient
from cilantro_ee.storage.contract import BlockchainDriver
from cilantro_ee.logger.base import get_logger
from cilantro_ee.networking.peers import PeerServer
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
            return True
        if reply[0] == 'n':
            return False


def reboot_config(key=None):
    if key is None:
        return

    myid = {'sk': key}

    with open('key.json', 'w') as outfile:
        json.dump(myid, outfile)


def restart():

    # Read configs
    rd_key = pathlib.Path(os.getcwd()) + '/key.json'

    try:
        f = open(str(rd_key), 'r')
        k = json.load(f)
        f.close()
    except IOError:
        log.info("Manual restart needed - Auto upgrade not Authorized")
        return

    assert 'sk' in k.keys(), 'No key found.'
    print(k)

    try:
        cfg_path = pathlib.Path(os.getcwd()) + '/key.json'
        f = open(str(cfg_path), 'r')
        cfg = json.load(f)
        f.close()
    except IOError:
        log.error("Config not found - restart manually")

    assert 'nodes' in cfg.keys(), 'No bootnodes found'
    assert 'version' in cfg.keys(), 'No pepper found'
    assert 'type' in cfg.keys(), 'No Node Type'
    print(cfg)

    bn = cfg['nodes']
    bn_str = ''

    for i in bn:
        bn_str = bn_str + " " + i

    cmd = f"cil start {cfg['type']} -k {k['sk']} -bn {bn_str}"

    print(cmd)
    #subprocess.run(cmd, shell=True)


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
            restart()
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
