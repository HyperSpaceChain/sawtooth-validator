# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import os
import sys
import argparse
import cmd
import pprint
import traceback
import tempfile
import logging
import shutil

from txnintegration.validator_network_manager import ValidatorNetworkManager
from txnintegration.utils import ExitError, parse_configuration_file, \
    prompt_yes_no, find_txn_validator

logger = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)


def parse_args(args):
    parser = argparse.ArgumentParser()

    # use system or dev paths...
    parser.add_argument('--validator',
                        help='Fully qualified path to the txnvalidator to run',
                        default=None)
    parser.add_argument('--config',
                        help='Base validator config file',
                        default=None)
    parser.add_argument('--count',
                        help='Number of validators to launch',
                        default=1,
                        type=int)
    parser.add_argument('--save-blockchain',
                        help='Save the blockchain to a file when the '
                             'network is shutdown. This is the name of the '
                             'tar.gz file that the blockchain will be saved '
                             'in. ',
                        default=None)
    parser.add_argument('--load-blockchain',
                        help='load an existing blockchain from file. This '
                             'is a file name that points to a tar.gz that '
                             'was generated from a previous run using the '
                             '--save-blockchain option.',
                        default=None)
    parser.add_argument('--data-dir',
                        help='Where to store the logs, data, etc for the '
                             'network',
                        default=None)
    parser.add_argument('--log-level',
                        help='LogLevel to run the validators at.',
                        default="WARNING")

    return parser.parse_args(args)


def configure(opts):
    scriptDir = os.path.dirname(os.path.realpath(__file__))

    # Find the validator to use
    if opts.validator is None:
        opts.validator = find_txn_validator()
        if not os.path.isfile(opts.validator):
            print("txnvalidator: {}".format(opts.validator))
            raise ExitError("Could not find txnvalidator.")
    else:
        if not os.path.isfile(opts.validator):
            print("txnvalidator: {}".format(opts.validator))
            raise ExitError("txnvalidator script does not exist.")

    validatorConfig = {}
    if opts.config is not None:
        if os.path.exists(opts.config):
            validatorConfig = parse_configuration_file(opts.config)
        else:
            raise ExitError("Config file does not exist: {}".format(
                opts.config))
    else:
        opts.config = os.path.realpath(os.path.join(scriptDir, "..", "etc",
                                                    "txnvalidator.js"))
        print("No config file specified, loading  {}".format(opts.config))
        if os.path.exists(opts.config):
            validatorConfig = parse_configuration_file(opts.config)
        else:
            raise ExitError(
                "Default config file does not exist: {}".format(opts.config))

    if opts.load_blockchain is not None:
        if not os.path.isfile(opts.load_blockchain):
            raise ExitError("Blockchain archive to load {} does not "
                            "exist.".format(opts.load_blockchain))

    # Create directory -- after the params have been validated
    if opts.data_dir is None:
        opts.data_dir_is_tmp = True  # did we make up a directory
        opts.data_dir = tempfile.mkdtemp()
    else:
        opts.data_dir = os.path.abspath(opts.data_dir)
        if not os.path.exists(opts.data_dir):
            os.makedirs(opts.data_dir)

    keys = [
        'NodeName',
        'Host',
        'HttpPort',
        'Port',
        'LogFile',
        'LogLevel',
        'KeyFile',
        "AdministrationNode",
        "DataDirectory",
        "GenesisLedger",
    ]
    if any(k in validatorConfig for k in keys):
        print "Overriding the following keys from validator configuration " \
              "file: {}".format(opts.config)
        for k in keys:
            if k in validatorConfig:
                print "\t{}".format(k)
                del validatorConfig[k]

    opts.count = max(1, opts.count)
    opts.validator_config = validatorConfig
    opts.validator_config['LogLevel'] = opts.log_level

    print "Configuration:"
    pp.pprint(opts.__dict__)


class ValidatorNetworkConsole(cmd.Cmd):
    pformat = '> '

    def __init__(self, vnm):
        self.prompt = 'launcher_cli.py> '
        cmd.Cmd.__init__(self)
        self.networkManager = vnm

    def do_config(self, args):
        """
        config
        :param args: index of the validator
        :return: Print the  validator configuration file
        """
        try:
            args = args.split()
            parser = argparse.ArgumentParser()
            parser.add_argument("id",
                                help='Validator index or node name',
                                default='0')
            options = parser.parse_args(args)

            id = options.id
            v = self.networkManager.validator(id)
            if v:
                v.dump_config()
            else:
                print "Invalid validator id: {}".format(args[0])
        except:
            print sys.exc_info()[0]

        return False

    def do_log(self, args):
        try:
            id = args
            v = self.networkManager.validator(id)
            if v:
                v.dump_log()
            else:
                print "Invalid validator  id: {}".format(args[0])
        except:
            print sys.exc_info()[0]

        return False

    def do_out(self, args):
        try:
            id = args[0]
            v = self.networkManager.validator(id)
            if v:
                v.dump_stdout()
            else:
                print "Invalid validator id: {}".format(args[0])
        except:
            print sys.exc_info()[0]

        return False

    def do_err(self, args):
        try:
            id = args[0]
            v = self.networkManager.validator(id)
            if v:
                v.dump_stderr()
            else:
                print "Invalid validator id: {}".format(args[0])
        except:
            print sys.exc_info()[0]

        return False

    def do_launch(self, args):
        """launch
        Launch another validator on the network
        """
        v = self.networkManager.launch_node()
        print("Validator {} launched.".format(v.Name))
        return False

    def do_launch_cmd(self, args):
        """lcmd
        Give the command to launch another validator on the network. This can
        be used for creating a node to debug on  the validator network.
        """
        v = self.networkManager.launch_node(False)
        print v.command
        return False

    def do_kill(self, args):
        pass

    def do_status(self, args):
        """status
        Show the status of the running validators
        """
        s = self.networkManager.status()
        return False

    def do_exit(self, args):
        """exit
        Shutdown the simulator and exit the command loop
        """
        return True

    def do_eof(self, args):
        print("")
        return self.do_exit(args)


def main():
    networkManager = None
    errorOccured = False
    try:
        opts = parse_args(sys.argv[1:])
    except:
        # argparse reports details on the parameter error.
        sys.exit(1)

    try:
        # Discover configuration
        configure(opts)

        networkManager = ValidatorNetworkManager(
            txnvalidator=opts.validator,
            cfg=opts.validator_config,
            dataDir=opts.data_dir,
            blockChainArchive=opts.load_blockchain)
        networkManager.launch_network(opts.count)

        # wait ...
        ctrl = ValidatorNetworkConsole(networkManager)
        ctrl.cmdloop("\nWelcome to the sawtooth txnvalidator network "
                     "manager interactive console")
    except KeyboardInterrupt:
        print "\nExiting"
    except ExitError as e:
        # this is an expected error/exit, don't print stack trace -
        # the code raising this exception is expected to have printed the error
        # details
        errorOccured = True
        print "\nFailed!\nExiting: {}".format(e)
    except:
        errorOccured = True
        traceback.print_exc()
        print "\nFailed!\nExiting: {}".format(sys.exc_info()[0])

    if networkManager:
        networkManager.shutdown()

    if opts.save_blockchain:
        print "Saving blockchain to {}".format(opts.save_blockchain)
        networkManager.pack_blockchain(opts.save_blockchain)

    # if dir was auto-generated
    if opts and "data_dir_is_tmp" in opts \
            and opts.data_dir_is_tmp \
            and os.path.exists(opts.data_dir):
        deleteTestDir = True
        if errorOccured:
            deleteTestDir = prompt_yes_no(
                "Do you want to delete the data dir(logs, configs, etc)")
        if deleteTestDir:
            print "Cleaning temp data store {}".format(opts.data_dir)
            if os.path.exists(opts.data_dir):
                shutil.rmtree(opts.data_dir)
        else:
            print "Data directory {}".format(opts.data_dir)
    else:
        print "Data directory {}".format(opts.data_dir)


if __name__ == "__main__":
    main()
