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

import subprocess
import urllib2
import os
import sys
import re
import json

from txnintegration.utils import generate_private_key
from txnintegration.utils import get_address_from_private_key_wif
from txnintegration.utils import human_size
from gossip.messages import shutdown_message
from txnserver import ledger_web_client


class ValidatorManager:
    """
    Manages a txnvalidator process
    contains logic to:
     - launch
     - shutdown
     - check status
     - detect errors
     - report log, stderr, and strout
    """

    def __init__(self, txnvalidater, config, dataDir, adminNode):
        self.txnvalidater = txnvalidater
        self.Id = config['id']
        self.Name = config['NodeName']
        self.config = config
        self.AdminNode = adminNode

        self.dataDir = dataDir

        # Generate key for validator
        self.Key = generate_private_key()
        self.Address = get_address_from_private_key_wif(self.Key)

    def launch(self, launch=True):
        self.Url = "http://{}:{}".format(self.config['Host'],
                                         self.config['HttpPort'])
        self.config['LogFile'] = os.path.join(self.dataDir,
                                              "{}.log".format(self.Name))
        self.logFile = self.config['LogFile']

        self.config['KeyFile'] = os.path.join(self.dataDir,
                                              "{}.wif".format(self.Name))
        if not os.path.isfile(self.config['KeyFile']):
            with open(self.config['KeyFile'], 'w') as fp:
                fp.write(self.Key)
                fp.write("\n")

        configFileName = "{}.json".format(self.Name)
        self.configFile = os.path.join(self.dataDir, configFileName)
        with open(self.configFile, 'w') as fp:
            json.dump(self.config, fp)

        args = [
            sys.executable,  # Fix for windows, where script are not executable
            self.txnvalidater,
            "--conf-dir",
            self.dataDir,
            "--config",
            configFileName
        ]

        # redirect stdout and stderror
        self.stdoutFile = os.path.join(self.dataDir,
                                       "{}.out".format(self.Name))
        self.stderrFile = os.path.join(self.dataDir,
                                       "{}.err".format(self.Name))

        self.command = " ".join(args)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        if launch:
            self.output = open(self.stdoutFile, 'w')
            self.outerr = open(self.stderrFile, 'w')
            self.handle = subprocess.Popen(args,
                                           stdout=self.output,
                                           stderr=self.outerr,
                                           env=env)
        else:
            self.handle = None

    def is_registered(self, url=None):
        if not url:
            url = self.Url
        url = "{}/store/EndpointRegistryTransaction".format(url)

        try:
            response = urllib2.urlopen(url)
        except:
            return False

        content = response.read()
        headers = response.info()
        response.close()
        if ('Content-Type' not in headers
                or headers['Content-Type'] != 'application/json'):
            return False

        idList = json.loads(content)
        if idList is not None:
            return self.Address in idList

        return False

    def shutdown(self, force=False):
        if self.handle:
            self.handle.poll()
            if not self.handle.returncode:
                if force:
                    try:
                        self.handle.kill()
                    except OSError:
                        pass  # ignore invalid process and other os type errors
                else:
                    self.post_shutdown()
        if self.output and not self.output.closed:
            self.output.close()
        if self.outerr and not self.outerr.closed:
            self.outerr.close()

    def post_shutdown(self):
        lwc = ledger_web_client.LedgerWebClient(self.Url)

        msg = shutdown_message.ShutdownMessage({})
        msg.SenderID = self.AdminNode.Address
        msg.sign_from_node(self.AdminNode)

        try:
            result = lwc.post_message(msg)
        except ledger_web_client.MessageException as me:
            print me

    def is_running(self):
        if self.handle:
            return self.handle.returncode is None
        return False

    def has_error(self):
        if self.handle:
            if self.handle.returncode:
                return True  # has exited
            else:
                err = os.stat(self.stderrFile)
                if err.st_size > 0:
                    return True  # has stderr output
                if self.has_log_error():
                    return True  # has log error msg output
            return False
        return True  # is not running

    def has_log_error(self):
        if os.path.exists(self.logFile):
            reg = re.compile("^\[[\d:]*, ([\d]*), .*]")
            with open(self.logFile, 'r') as fin:
                for line in fin:
                    match = reg.search(line)
                    if match and int(match.group(1)) >= 50:
                        return True
        return False

    def status(self):
        st = "UNK  "
        if self.handle:
            rc = self.handle.returncode
            if rc:
                st = " rc:{}".format(rc)
            else:
                st = " pid:{}".format(self.handle.pid)

        log = ""
        if os.path.exists(self.logFile):
            s = os.stat(self.logFile)
            if s.st_size > 0:
                log = "LOG: {}".format(human_size(s.st_size))
        out = ""
        if os.path.exists(self.stdoutFile):
            s = os.stat(self.stdoutFile)
            if s.st_size > 0:
                out = "LOG: {}".format(human_size(s.st_size))
        err = ""
        if os.path.exists(self.stderrFile):
            s = os.stat(self.stderrFile)
            if s.st_size > 0:
                err = "LOG: {}".format(human_size(s.st_size))
        errors = "ERROR" if self.has_error() else ""

        print("{}: {} {} {} {} {}".format(self.Id, st, out, err, log, errors))

    def dump_config(self):
        with open(self.configFile, 'r') as fin:
            print fin.read()

    def dump_log(self):
        if os.path.exists(self.logFile):
            with open(self.logFile, 'r') as fin:
                print fin.read()

    def dump_stdout(self):
        if os.path.exists(self.stdoutFile):
            with open(self.stdoutFile, 'r') as fin:
                print fin.read()

    def dump_stderr(self):
        if os.path.exists(self.stderrFile):
            with open(self.stderrFile, 'r') as fin:
                print fin.read()
