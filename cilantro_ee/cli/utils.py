import os
import json
import sys
import psutil
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

def version_reboot(bn):
    driver = BlockchainDriver()
    active_upgrade = driver.get_var(contract='upgrade', variable='upg_lock', mark=False)

    if active_upgrade is True:
        target_version = driver.get_var(contract='upgrade', variable='upg_pepper', mark=False)
    else:
        target_version = None
        assert target_version is None, "New version target Cannot be None"
        return

    log.info("peer list {}".format(bn))
    log.info("target version {}".format(target_version))

    info = {}
    info['nodes'] = [strip_ip(i) for i in bn]
    info['version'] = target_version

    with open('network_info.txt', 'w') as outfile:
        json.dump(info, outfile)

    # Find cil process
    PNAME = 'cil'
    for proc in psutil.process_iter():
        # check whether the process name matches
        if proc.name() == PNAME:
            print("{} : {} proc shutting down".format(proc.pid, proc.name()))
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
