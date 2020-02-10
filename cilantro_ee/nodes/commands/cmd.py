import argparse
from cilantro_ee.crypto.wallet import Wallet


class Cilparser:
    def __init__(self):
        self.pkg = args.pkg_hash
        self.vote = args.vote
        self.ready = args.ready

        print(self.pkg, self.vote, self.ready)

    def trigger(self):
        print('pkg ->', self.pkg)
        return True

    def check_vote(self, vk = None):
        print('vote ->', vk)
        return True

    def check_ready_quorum(self, vk = None):
        print('ready ->', vk)
        return True


def setup_cilparser(parser):
    # create parser for update commands
    subparser = parser.add_subparsers(title = 'subcommands', description='Network update commands',
                                      help = 'Shows set of update cmd options')

    upd_parser = subparser.add_parser('update')

    upd_parser.add_argument('-t', '--trigger', dest = 'pkg_hash', nargs = '?', type =str,
                            help='str: Notify network of new update with given pkg_hash')

    upd_parser.parse_args('--trigger'.split())

    upd_parser.add_argument('-v', '--vote', action = 'store_true', default = False,
                            help='Bool : Register consent for network version upgrade')

    upd_parser.add_argument('-r', '--ready', action = 'store_true', default = False,
                            help='Bool : Notify network upgrade ready')

    # create parser for view commands
        #TODO
    # create parser for node admin commands
        #TODO
    # create parser for stats commands
        #TODO
    # create parser for debug/logging view
        #TODO
    return True


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description = "Lamden Commands", prog='cil')
    setup_cilparser(parser)
    args = parser.parse_args()

    # implementation

    shell = Cilparser()

    if args.pkg_hash:
        shell.trigger()
        # execute upgrade contract

    if args.vote:
        res = shell.check_vote(vk = 'asdfadf')

    if args.ready:
        print(args)
        res = shell.check_ready_quorum(vk = 'sdfafda')