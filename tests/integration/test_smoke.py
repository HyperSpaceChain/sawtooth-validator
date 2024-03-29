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

import random
import traceback
import unittest
import os
import time
from twisted.web import http

from txnintegration.utils import generate_private_key
from txnintegration.utils import Progress
from txnintegration.utils import TimeOut
from txnintegration.integer_key_client import IntegerKeyClient
from txnintegration.integer_key_state import IntegerKeyState
from txnintegration.validator_network_manager import ValidatorNetworkManager

ENABLE_INTEGRATION_TESTS = False
if os.environ.get("ENABLE_INTEGRATION_TESTS", False) == "1":
    ENABLE_INTEGRATION_TESTS = True


class IntKeyLoadTest:
    def __init__(self):
        pass

    def _get_client(self):
        return self.clients[random.randint(0, len(self.clients) - 1)]

    def _has_uncommitted_transactions(self):
        remaining = []
        for t in self.transactions:
            status = self.clients[0].headrequest('/transaction/{0}'.format(t))
            if status != http.OK:
                remaining.append(t)

        self.transactions = remaining
        return len(self.transactions)

    def _wait_for_transaction_commits(self):
        to = TimeOut(120)
        txnCnt = len(self.transactions)
        with Progress("Waiting for transactions to commit") as p:
            while not to() and txnCnt > 0:
                p.step()
                time.sleep(1)
                self._has_uncommitted_transactions()
                txnCnt = len(self.transactions)

        if txnCnt != 0:
            if len(self.transactions) != 0:
                print "Uncommitted transactions: ", self.transactions
            raise Exception("{} transactions failed to commit in {}s".format(
                txnCnt, to.WaitTime))

    def setup(self, urls, numKeys):
        self.localState = {}
        self.transactions = []
        self.clients = []
        self.state = IntegerKeyState(urls[0])

        with Progress("Creating clients") as p:
            for u in urls:
                key = generate_private_key()
                self.clients.append(IntegerKeyClient(u, keystring=key))
                p.step()

        with Progress("Creating initial key values") as p:
            for n in range(1, numKeys + 1):
                n = str(n)
                c = self._get_client()
                v = random.randint(5, 1000)
                self.localState[n] = v
                txnid = c.set(n, v)
                if txnid is None:
                    raise Exception("Failed to set {} to {}".format(n, v))
                self.transactions.append(txnid)

        self._wait_for_transaction_commits()

    def run(self, rounds=1):
        self.state.fetch()

        inc = True
        keys = self.state.State.keys()

        for r in range(0, rounds):
            for c in self.clients:
                c.CurrentState.fetch()
            print "Round {}".format(r)
            for k in keys:
                c = self._get_client()
                self.localState[k] += 2
                txnid = c.inc(k, 2)
                if txnid is None:
                    raise Exception(
                        "Failed to inc key:{} value:{} by 2".format(
                            k, self.localState[k]))
                self.transactions.append(txnid)
            for k in keys:
                c = self._get_client()
                self.localState[k] -= 1
                txnid = c.dec(k, 1)
                if txnid is None:
                    raise Exception(
                        "Failed to dec key:{} value:{} by 1".format(
                            k, self.localState[k]))
                self.transactions.append(txnid)

            self._wait_for_transaction_commits()

    def validate(self):
        self.state.fetch()

        print "Validating IntegerKey State"
        for k, v in self.state.State.iteritems():
            if self.localState[k] != v:
                print "key {} is {} expected to be {}".format(
                    k, v, self.localState[k])
            assert self.localState[k] == v


class TestSmoke(unittest.TestCase):
    @unittest.skipUnless(ENABLE_INTEGRATION_TESTS, "integration test")
    def test_intkey_load(self):
        vnm = None
        try:
            vnm = ValidatorNetworkManager(httpPort=9000, udpPort=9100)
            vnm.launch_network(5)

            print "Testing transaction load."
            test = IntKeyLoadTest()
            test.setup(vnm.urls(), 100)
            test.run(2)
            test.validate()
            vnm.shutdown()
        except Exception as e:
            print "Exception encountered in test case."
            traceback.print_exc()
            if vnm:
                vnm.shutdown()
            vnm.create_result_archive("TestSmokeResults.tar.gz")
            print "Validator data and logs preserved in: " \
                  "TestSmokeResults.tar.gz"
            raise e
