import argparse
from cilantro_ee.cli.start import start_node, join_network
# from cilantro_ee.cli.update import verify_access, verify_pkg, trigger, vote, check_ready_quorum
from cilantro_ee.storage import BlockStorage
from contracting.client import ContractDriver


def flush(args):
    if args.storage_type == 'blocks':
        BlockStorage().drop_collections()
        print('All blocks deleted.')
    elif args.storage_type == 'state':
        ContractDriver().flush()
        print('State deleted.')
    elif args.storage_type == 'all':
        b = BlockStorage()
        dbs = b.client.database_names()
        for db in dbs:
            if db == 'admin' or db == 'config':
                continue
            b.client.drop_database(db)

        ContractDriver().flush()
        print('All blocks deleted.')
        print('State deleted.')
    else:
        print('Invalid option. < blocks | state | all >')


def setup_cilparser(parser):
    # create parser for update commands
    subparser = parser.add_subparsers(title='subcommands', description='Network update commands',
                                      help='Shows set of update cmd options', dest='command')

    start_parser = subparser.add_parser('start')

    start_parser.add_argument('node_type', type=str)
    start_parser.add_argument('-k', '--key', type=str)
    start_parser.add_argument('-c', '--constitution', type=str, default='~/constitution.json')
    start_parser.add_argument('-wp', '--webserver_port', type=int, default=18080)
    start_parser.add_argument('-p', '--pid', type=int, default=-1)
    start_parser.add_argument('-b', '--bypass_catchup', type=bool, default=False)

    flush_parser = subparser.add_parser('flush')
    flush_parser.add_argument('storage_type', type=str)

    join_parser = subparser.add_parser('join')
    join_parser.add_argument('node_type', type=str)
    join_parser.add_argument('-k', '--key', type=str)
    join_parser.add_argument('-m', '--mn_seed', type=str)
    join_parser.add_argument('-mp', '--mn_seed_port', type=int, default=18080)
    join_parser.add_argument('-wp', '--webserver_port', type=int, default=18080)

    return True


def main():
    parser = argparse.ArgumentParser(description="Lamden Commands", prog='cil')
    setup_cilparser(parser)
    args = parser.parse_args()

    # implementation
    if vars(args).get('command') is None:
        print('Howdy.︎')
        return

    if args.command == 'start':
        start_node(args)

    elif args.command == 'flush':
        flush(args)

    elif args.command == 'join':
        join_network(args)



if __name__ == '__main__':
    main()
