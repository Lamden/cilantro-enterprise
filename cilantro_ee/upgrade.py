from contracting.client import ContractingClient
from cilantro_ee.logger.base import get_logger
import cilantro_ee
import contracting
import os
from cilantro_ee.cli.utils import version_reboot
from cilantro_ee.cli.utils import build_pepper, run_install, get_version
import importlib


class UpgradeManager:
    def __init__(self, client: ContractingClient, testing=False):
        self.client = client
        self.enabled = None
        self.log = get_logger('UPGRADE')

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
        self.upgrade = False
        self.testing = testing

    def version_check(self):
        # check for trigger
        if self.testing:
            self.log.info(f'# Master votes: {self.masternode_votes}, '
                          f'# Del. votes: {self.delegate_votes}, '
                          f'Test Name: {self.test_name}')
            if self.vote_consensus:
                self.log.info(f'Rebooting Node with new verions: '
                              f'CIL -> {self.branch_name}, CON -> {self.contracting_branch_name}')
            return

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

                self.log.info(f'Old CIL branch={old_branch_name}, '
                              f'Old contract branch={old_contract_name}, '
                              f' Only contract update={only_contract}')

                if version_reboot(self.branch_name, self.contracting_branch_name, only_contract):
                    p = build_pepper(cil_path)
                    if self.pepper != p:
                        self.log.error(f'peppers mismatch: {self.pepper} != {p}')
                        self.log.error(f'Restore previous versions: {old_branch_name} -> {old_contract_name}')

                        version_reboot(old_branch_name, old_contract_name, only_contract)
                        self.reset()
                    else:
                        self.log.info('Pepper OK. restart new version')

                        self.upgrade = True
                        run_install(only_contract)

                        self.reset()

                        if not only_contract:
                            importlib.reload(cilantro_ee)
                        importlib.reload(contracting)

                        self.log.info(f'New branch {self.branch_name} was reloaded OK.')
                        self.upgrade = False

                else:
                    self.log.error(f'Update failed. Old branches restored.')
                    version_reboot(old_branch_name, old_contract_name)
                    self.reset()

                self.reset()

    def reset(self):
        self.log.info('Upgrade process has concluded.')

        self.client.set_var(contract='upgrade', variable='upg_init_time', value=None)
        self.client.set_var(contract='upgrade', variable='upg_consensus', value=False)

        self.client.set_var(contract='upgrade', variable='upg_lock', value=False)
        self.client.set_var(contract='upgrade', variable='upg_pepper', value=None)

        self.client.set_var(contract='upgrade', variable='branch_name', value=None)
        self.client.set_var(contract='upgrade', variable='c_branch_name', value=None)

        self.client.set_var(contract='upgrade', variable='mn_vote', value=0)
        self.client.set_var(contract='upgrade', variable='dl_vote', value=0)
        self.client.set_var(contract='upgrade', variable='tot_mn', value=0)
        self.client.set_var(contract='upgrade', variable='tot_dl', value=0)

        self.log.info('Reset upgrade contract variables.')

