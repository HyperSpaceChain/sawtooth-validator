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
import re
import sys
import warnings

import gossip.config
from gossip.common import json2dict
from gossip.config import AggregateConfig
from gossip.config import load_config_files


def parse_configuration_files(cfiles, search_path):
    cfg = {}
    files_found = []
    files_not_found = []

    for cfile in cfiles:
        filename = None
        for directory in search_path:
            if os.path.isfile(os.path.join(directory, cfile)):
                filename = os.path.join(directory, cfile)
                break

        if filename is None:
            files_not_found.append(cfile)
        else:
            files_found.append(filename)

    if len(files_not_found) > 0:
        warnings.warn(
            "Unable to locate the following configuration files: "
            "{0} (search path: {1})".format(
                ", ".join(files_not_found), ", ".join(map(os.path.realpath,
                                                          search_path))))
        sys.exit(-1)

    for filename in files_found:
        try:
            cfg.update(parse_configuration_file(filename))
        except IOError as detail:
            warnings.warn("Error parsing configuration file %s; IO error %s" %
                          (filename, str(detail)))
            sys.exit(-1)
        except ValueError as detail:
            warnings.warn("Error parsing configuration file %s; value error %s"
                          % (filename, str(detail)))
            sys.exit(-1)
        except NameError as detail:
            warnings.warn("Error parsing configuration file %s; name error %s"
                          % (filename, str(detail)))
            sys.exit(-1)
        except:
            warnings.warn('Error parsing configuration file %s; %s' %
                          (filename, sys.exc_info()[0]))
            sys.exit(-1)

    return cfg


def parse_configuration_file(filename):
    cpattern = re.compile('##.*$')

    with open(filename) as fp:
        lines = fp.readlines()

    text = ""
    for line in lines:
        text += re.sub(cpattern, '', line) + ' '

    return json2dict(text)


def get_validator_configuration(config_files,
                                options_config,
                                os_name=os.name,
                                config_files_required=True):
    env_config = CurrencyEnvConfig()

    default_config = ValidatorDefaultConfig(os_name=os_name)

    conf_dir = AggregateConfig(
        configs=[default_config, env_config, options_config]).resolve(
            {'home': 'CurrencyHome'})['ConfigDirectory']

    # Determine the configuration file search path
    search_path = [conf_dir, '.', os.path.join(
        os.path.dirname(__file__), "..", "etc")]

    file_configs = load_config_files(config_files, search_path,
                                     config_files_required)

    config_list = [default_config]
    config_list.extend(file_configs)
    config_list.append(env_config)
    config_list.append(options_config)

    cfg = AggregateConfig(configs=config_list)
    resolved = cfg.resolve({
        'home': 'CurrencyHome',
        'host': 'CurrencyHost',
        'node': 'NodeName',
        'base': 'BaseDirectory',
        'conf_dir': 'ConfigDirectory',
        'data_dir': 'DataDirectory',
        'log_dir': 'LogDirectory',
        'key_dir': 'KeyDirectory'
    })
    return resolved


class ValidatorDefaultConfig(gossip.config.Config):
    def __init__(self, os_name=os.name):
        super(ValidatorDefaultConfig, self).__init__(name="default")

        if 'CURRENCYHOME' in os.environ:
            self['ConfigDirectory'] = '{home}/etc'
            self['LogDirectory'] = '{home}/logs'
            self['DataDirectory'] = '{home}/data'
            self['KeyDirectory'] = '{home}/keys'
        elif os_name == 'nt':
            base_dir = 'C:\\Program Files (x86)\\Intel\\sawtooth-validator\\'
            self['ConfigDirectory'] = '{0}conf'.format(base_dir)
            self['LogDirectory'] = '{0}logs'.format(base_dir)
            self['DataDirectory'] = '{0}data'.format(base_dir)
            self['KeyDirectory'] = '{0}conf\\keys'.format(base_dir)
        else:
            self['ConfigDirectory'] = '/etc/sawtooth-validator'
            self['LogDirectory'] = '/var/log/sawtooth-validator'
            self['DataDirectory'] = '/var/lib/sawtooth-validator'
            self['KeyDirectory'] = '/etc/sawtooth-validator/keys'

        self['BaseDirectory'] = os.path.abspath(os.path.dirname(__file__))
        self['CurrencyHost'] = "localhost"


class CurrencyEnvConfig(gossip.config.EnvConfig):
    def __init__(self):
        super(CurrencyEnvConfig, self).__init__([
            ('CURRENCYHOME', 'CurrencyHome'),
            ('CURRENCY_CONF_DIR', 'ConfigDirectory'),
            ('CURRENCY_LOG_DIR', 'LogDirectory'),
            ('CURRENCY_DATA_DIR', 'DataDirectory'),
            ('HOSTNAME', 'CurrencyHost')
        ])
