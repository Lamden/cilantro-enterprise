from contracting.client import ContractingClient
from cilantro_ee.cli.utils import version_reboot


class UpgradeManager:
    def __init__(self, client: ContractingClient):
        self.client = client
        self.enabled = self.client.get_contract('upgrade') is not None
        self.contract = self.client.get_contract('upgrade')

    def version_check(self):
        if self.enabled and self.vote_consensus:
            version_reboot()

    @property
    def active_upgrade(self):
        return self.contract.quick_read('upg_lock')

    @property
    def vote_consensus(self):
        return self.contract.quick_read('upg_consensus')

    @property
    def masternode_votes(self):
        mn_vote = self.contract.quick_read('mn_vote')
        if mn_vote is None:
            return 0
        return mn_vote

    @property
    def delegate_votes(self):
        dl_vote = self.contract.quick_read('dl_votes')
        if dl_vote is None:
            return 0
        return dl_vote
