#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#
# Copyright 2015 Nandaja Varma <nvarma@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
#
#    yaml_writer.py
#    -------------
#    YamlWriter is a helper class used by VarFileGenerator to write
#    all the necessary sections and options into the yaml file
#    as per specified in the configuration file
#

import yaml
from conf_parser import ConfigParseHelpers
from global_vars import Global
from helpers import Helpers


class YamlWriter(ConfigParseHelpers):

    def __init__(self, bricks, config, filename, filetype):
        self.bricks = bricks
        self.config = config
        self.filename = filename
        self.filetype = filetype
        self.device_count = len(bricks)
        self.mountpoints = self.section_data_gen('mountpoints', 'Mount Point')
        self.write_sections()

    def write_sections(self):
        '''
        device names, vg names, lv names, pool names, mount point,
        everything is read into a dictionary section_dict, so the association
        can be maintained between all these things. Association as in,
        /dev/vgname1/lvname1 is to be mounted at mount_point1 etc
        '''
        if self.bricks:
            sections = ['vgs', 'lvs', 'pools']
            section_names = ['Volume Group', 'Logical Volume',
                             'Logical Pool']
            self.section_dict = {'bricks': self.bricks,
                                 'mountpoints': self.mountpoints}
            for section, section_name in zip(sections, section_names):
                self.section_dict[section] = self.section_data_gen(
                    section,
                    section_name)
            self.section_dict['lvols'] = ['/dev/%s/%s' % (i, j) for i, j in
                                          zip(self.section_dict['vgs'],
                                              self.section_dict['lvs'])]
            listables_in_yaml = {
                key: self.section_dict[key] for key in [
                    'vgs',
                    'bricks',
                    'mountpoints',
                    'lvols']}
            self.iterate_dicts_and_yaml_write(listables_in_yaml)
            self.yaml_dict_data_write()
            self.perf_spec_data_write()
        elif self.mountpoints:
            '''
            If anyone wishes to just give the mountpoints directly
            without setting up the backend, only mountpoints option
            need to be given in the config file. It will skip
            the back-end setup
            '''
            Global.do_setup_backend = False
            self.iterate_dicts_and_yaml_write(
                {'mountpoints': self.mountpoints})
        else:
            print "Error: Device names for backend setup or mount point " \
                "details for gluster deployement not provided. Exiting."
            self.cleanup_and_quit()

    def insufficient_param_count(self, section, count):
        print "Error: Please provide %s names for %s devices " \
            "else leave the field empty" % (section, count)
        self.cleanup_and_quit()

    def split_comma_seperated_options(self, section, option, reqd):
        options = self.config_section_map(self.config, section, option, reqd)
        if options:
            return filter(None, options.split(','))
        return []

    def get_options(self, section, required):
        if self.filetype == 'group_vars':
            return self.config_get_options(self.config, section, required)
        else:
            return self.split_comma_seperated_options(
                self.filename.split('/')[-1], section,
                required)

    def section_data_gen(self, section, section_name):
        options = self.get_options(section, False)
        if options:
            if len(options) < self.device_count:
                return self.insufficient_param_count(
                    section_name,
                    self.device_count)
        else:
            pattern = {'vgs': 'RHS_vg',
                       'pools': 'RHS_pool',
                       'lvs': 'RHS_lv',
                       'mountpoints': '/rhs/brick'
                       }[section]
            for i in range(1, self.device_count + 1):
                options.append(pattern + str(i))
        return options

    def iterate_dicts_and_yaml_write(self, data_dict, keep_format=False):
        # Just a pretty wrapper over create_yaml_dict to iterate over dicts
        for key, value in data_dict.iteritems():
            self.create_yaml_dict(key, value, keep_format)

    def create_yaml_dict(self, section, data, keep_format=True):
        '''
        This method is called if in the playbook yaml,
        the options are to be written as a list
        '''
        data_dict = {}
        data_dict[section] = data
        self.write_yaml(data_dict, keep_format)

    def yaml_dict_data_write(self):
        '''
        Matter complicates when the data are to be written as a dictionary
        in the yaml. for the data with above mentioned associations are
        to be written as a dictionary itself in the yaml, the dictionary
        section_dict is iterated keeping the associations intact, and
        multiple lists are created for vgs, lvs, pools, mountpoints
        '''
        # Just a pretty way to initialise 4 empty lists
        vgnames, mntpaths, lvpools, pools = ([] for i in range(4))
        for i, vg in enumerate(self.section_dict['vgs']):
            vgnames.append({'brick': self.section_dict['bricks'][i], 'vg': vg})
            mntpaths.append({'path': self.section_dict['mountpoints'][i],
                             'device': self.section_dict['lvols'][i]})
            lvpools.append({'pool': self.section_dict['pools'][i], 'vg': vg,
                            'lv': self.section_dict['lvs'][i]})
            pools.append({'pool': self.section_dict['pools'][i], 'vg': vg})
        data_dict = {
            'vgnames': vgnames,
            'lvpools': lvpools,
            'mntpath': mntpaths,
            'pools': pools}
        self.iterate_dicts_and_yaml_write(data_dict, True)

    def gluster_vol_spec(self, config):
        self.filename = Global.group_file
        self.config = config
        self.clients = self.split_comma_seperated_options('clients', 'hosts',
                                                          False)
        if not self.clients:
            log_level = 'Warning' if Global.do_setup_backend else 'Error'

            print "%s: Client hosts are not specified. Cannot do GlusterFS " \
                "deployement." % log_level
            Global.do_gluster_deploy = False
            return
        if not Global.do_setup_backend:
            print "Warning: Since no brick data is provided, we cannot do a "\
                "backend setup. Continuing with gluster deployement using "\
                " the mount points provided"
        self.client_mntpts = self.split_comma_seperated_options(
            'clients', 'mountpoints',
            False) or ['/mnt/gluster']
        self.write_volume_conf_data()
        self.write_client_conf_data()

    def write_volume_conf_data(self):
        volume = {}
        volume['volname'] = self.config_section_map(self.config, 'volume',
                                                    'volname') or 'glustervol'
        volume['transport'] = self.config_section_map(self.config, 'volume',
                                                      'transport') or 'tcp'
        volume['replica'] = self.config_section_map(self.config, 'volume',
                                                    'replica') or 'no'
        volume['disperse'] = self.config_section_map(self.config, 'volume',
                                                     'disperse') or 'no'
        replica_count_necessary = True if volume['replica'] != 'no' else False
        volume['replica_count'] = self.config_section_map(
            self.config,
            'volume',
            'replica_count',
            replica_count_necessary) or 0
        volume['arbiter_count'] = self.config_section_map(
            self.config,
            'volume',
            'arbiter-count') or 0
        volume['disperse_count'] = self.config_section_map(
            self.config,
            'volume',
            'disperse_count') or 0
        volume['redundancy_count'] = self.config_section_map(
            self.config,
            'volume',
            'redundancy_count') or 0
        self.iterate_dicts_and_yaml_write(volume)

    def write_client_conf_data(self):
        '''
        client hostnames or IP should also be in the inventory file since
        mounting is to be done in the client host machines
        Also, host_var files are to be created if multiple clients
        have different mount points for gluster volume
        '''
        self.write_config('clients', self.clients, Global.inventory)
        if len(self.client_mntpts) != len(self.clients) and len(
                self.client_mntpts) != 1:
            print "Error: Provide volume mount points in each client " \
                "or a common mount point for all the clients. "
            self.cleanup_and_quit()
        if len(self.client_mntpts) == 1:
            gluster = dict(client_mount_points=self.client_mntpts)
            self.iterate_dicts_and_yaml_write(gluster)
        else:
            for client, mntpnt in zip(self.clients, self.client_mntpts):
                gluster = dict()
                self.filename = self.get_file_dir_path(
                    Global.host_vars_dir, client)
                gluster = dict(client_mount_points=mntpnt)
                self.iterate_dicts_and_yaml_write(gluster)

    def perf_spec_data_write(self):
        '''
        Now this one looks dirty. Couldn't help it.
        This one reads the performance related data like
        number of data disks and stripe unit size  if
        the option disk type is provided in the config.
        Some calculations are made as to enhance
        performance
        '''
        disktype = self.config_get_options(self.config,
                                           'disktype', False)
        if disktype:
            perf = dict(disktype=disktype[0].lower())
            if perf['disktype'] not in ['raid10', 'raid6', 'jbod']:
                print "Error: Unsupported disk type!"
                self.cleanup_and_quit()
            if perf['disktype'] != 'jbod':
                perf['diskcount'] = int(self.get_options('diskcount', True)[0])
                stripe_size_necessary = {'raid10': False,
                                         'raid6': True
                                         }[perf['disktype']]
                stripe_size = self.get_options('stripesize',
                                               stripe_size_necessary)
                if stripe_size:
                    perf['stripesize'] = int(stripe_size[0])
                    if perf['disktype'] == 'raid10' and perf[
                            'stripesize'] != 256:
                        print "Warning: We recommend a stripe unit size of 256KB " \
                            "for RAID 10"
                else:
                    perf['stripesize'] = 256
                perf['dalign'] = {
                    'raid6': perf['stripesize'] * perf['diskcount'],
                    'raid10': perf['stripesize'] * perf['diskcount']
                }[perf['disktype']]
        else:
            perf = dict(disktype='jbod')
            perf['dalign'] = 256
            perf['diskcount'] = perf['stripesize'] = 0
        perf['profile'] = self.config_get_options(
            self.config,
            'tune-profile',
            False) or 'rhs-high-throughput'
        self.iterate_dicts_and_yaml_write(perf)

    def write_host_names(self, config, hosts):
        self.config = config
        self.filename = Global.group_file
        self.create_yaml_dict('hosts', hosts, False)

    def write_yaml(self, data_dict, data_flow):
        with open(self.filename, 'a+') as outfile:
            if not data_flow:
                outfile.write(
                    yaml.dump(
                        data_dict,
                        default_flow_style=data_flow))
            else:
                outfile.write(yaml.dump(data_dict))