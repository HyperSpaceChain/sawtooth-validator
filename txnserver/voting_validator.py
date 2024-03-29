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

import logging

from txnserver import validator
from journal.consensus.quorum import quorum_journal

logger = logging.getLogger(__name__)


class VotingValidator(validator.Validator):
    EndpointDomain = '/VotingValidator'

    def __init__(self, config, windows_service=False):
        super(VotingValidator, self).__init__(config, windows_service)

    def initialize_ledger_specific_configuration(self):
        """
        Initialize any ledger type specific configuration options, expected to
        be overridden
        """

        pass

    def initialize_ledger_from_node(self, node):
        """
        Initialize the ledger object for the local node, expected to be
        overridden
        """
        self.Ledger = quorum_journal.QuorumJournal(node, self.Config)

        nodelist = self.get_endpoints(0, self.EndpointDomain)
        for node in nodelist:
            self.Ledger.add_quorum_node(node)
