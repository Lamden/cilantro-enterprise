import subprocess

from checksumdir import dirhash
from contracting.client import ContractingClient

from cilantro_ee.logger.base import get_logger
import cilantro_ee
import contracting
import os
import importlib
import sys


def reload_module(module_name: str):
    for name, module in sys.modules.items():
        if name.startswith(module_name):
            importlib.reload(module)


class UpgradeManager:
    def __init__(self, client: ContractingClient, wallet=None, node_type=None, constitution_filename=None, webserver_port=None, testing=False):
        self.client = client
        self.enabled = None
        self.log = get_logger('UPGRADE')

        self.node_type = node_type
        self.constitution_filename = constitution_filename
        self.webserver_port = webserver_port
        self.wallet = wallet

        self.refresh()

        self.upgrade = False
        self.testing = testing

    def refresh(self):
        self.active_upgrade = self.client.get_var(contract='upgrade', variable='upg_lock')
        self.vote_consensus = self.client.get_var(contract='upgrade', variable='upg_consensus')

        self.masternode_votes = self.client.get_var(contract='upgrade', variable='mn_vote')
        if self.masternode_votes is None:
            self.masternode_votes = 0

        self.delegate_votes = self.client.get_var(contract='upgrade', variable='dl_votes')
        if self.delegate_votes is None:
            self.delegate_votes = 0

        self.test_name = self.client.get_var(contract='upgrade', variable='test_name')
        self.branch_name = self.client.get_var(contract='upgrade', variable='branch_name')
        self.contracting_branch_name = self.client.get_var(contract='upgrade', variable='c_branch_name')

        self.pepper = self.client.get_var(contract='upgrade', variable='upg_pepper')

    def version_check(self):
        self.refresh()

        enabled = self.client.get_contract('upgrade') is not None
        if enabled:
            self.log.info(f'# Master votes: {self.masternode_votes}, '
                          f'# Del. votes: {self.delegate_votes}, '
                          f'Test Name: {self.test_name}')

            # check for vote consensys
            if self.vote_consensus:
                self.log.info(f'Rebooting Node with new verions: '
                              f'CIL -> {self.branch_name}, CON -> {self.contracting_branch_name}')

                cil_path = os.path.dirname(cilantro_ee.__file__)

                self.log.info(f'CIL_PATH={cil_path}')
                self.log.info(f'CONTRACTING_PATH={os.path.dirname(contracting.__file__)}')

                old_branch_name = get_version()
                old_contract_name = get_version(os.path.join(os.path.dirname(contracting.__file__), '..'))
                only_contract = self.branch_name == old_branch_name
                if self.contracting_branch_name == old_contract_name and self.branch_name == old_branch_name:
                    self.log.info(f'New verions is already installed')
                else:
                    self.log.info(f'Old CIL branch={old_branch_name}, '
                                  f'Old contract branch={old_contract_name}, '
                                  f' Only contract update={only_contract}')

                    if version_reboot(self.branch_name, self.contracting_branch_name, only_contract):
                        p = build_pepper(cil_path)
                        if self.pepper != p:
                            self.log.error(f'peppers mismatch: {self.pepper} != {p}')
                            self.log.error(f'Restore previous versions: {old_branch_name} -> {old_contract_name}')

                            version_reboot(old_branch_name, old_contract_name, only_contract)
                            self.reset_contract_variables()
                        else:
                            self.log.info('Pepper OK. restart new version')

                            self.upgrade = True
                            run_install(only_contract)

                            self.reset_contract_variables()

                            if not self.testing:
                                self.restart_node()

                            self.log.info(f'New branch {self.branch_name} was reloaded OK.')
                            self.upgrade = False

                    else:
                        self.log.error(f'Update failed. Old branches restored.')
                        version_reboot(old_branch_name, old_contract_name)
                        self.reset_contract_variables()

                    # Restart goes here

                self.reset_contract_variables()

    def reset_contract_variables(self):
        self.log.info('Upgrade process has concluded.')

        self.client.raw_driver.driver.set('upgrade.upg_init_time', value=None)
        self.client.raw_driver.driver.set('upgrade.upg_consensus', value=False)

        self.client.raw_driver.driver.set('upgrade.upg_lock', value=False)
        self.client.raw_driver.driver.set('upgrade.upg_pepper', value=None)

        self.client.raw_driver.driver.set('upgrade.branch_name', value=None)
        self.client.raw_driver.driver.set('upgrade.c_branch_name', value=None)

        self.client.raw_driver.driver.set('upgrade.mn_vote', value=0)
        self.client.raw_driver.driver.set('upgrade.dl_vote', value=0)
        self.client.raw_driver.driver.set('upgrade.tot_mn', value=0)
        self.client.raw_driver.driver.set('upgrade.tot_dl', value=0)

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        self.log.info('Reset upgrade contract variables.')

    def restart_node(self):
        self_pid = os.getpid()
        subprocess.check_call(
            ['nohup',
             'cil', 'start', self.node_type,
             '-k', self.wallet.signing_key,
             '-c', self.constitution_filename,
             '-wp', self.webserver_port,
             '-p', self_pid,
             '-b', True,
             '&']
        )


def build_pepper(pkg_dir_path=os.path.dirname(cilantro_ee.__file__)):
    if pkg_dir_path is None:
        pkg_dir_path = '../../cilantro_ee'

    pepper = dirhash(pkg_dir_path, 'sha256', excluded_extensions=['pyc'])
    return pepper


def verify_cil_pkg(pkg_hash):
    current_pepper = build_pepper(pkg_dir_path=os.path.dirname(cilantro_ee.__file__))

    if current_pepper == pkg_hash:
        return True
    else:
        return False


def run(*args):
    return subprocess.check_call(['git'] + list(args))


def run_install(only_contract=False):
    if not only_contract:
        path = os.path.join(os.path.dirname(cilantro_ee.__file__),  '..')
        os.chdir(f'{path}')
        subprocess.check_call(['python3', "setup.py", "develop"])  # "install"

    path2 = os.path.join(os.path.dirname(contracting.__file__),  '..')
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
