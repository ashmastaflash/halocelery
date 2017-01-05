import cloudpassage
import haloevents
import os
from utility import Utility as util


class Halo(object):
    def __init__(self):
        self.halo_api_key = os.getenv("HALO_API_KEY")
        self.halo_api_secret = os.getenv("HALO_API_SECRET_KEY")
        self.session = cloudpassage.HaloSession(self.halo_api_key,
                                                self.halo_api_secret)

    def list_all_servers(self):
        servers = cloudpassage.Server(self.session)
        return servers.list_all()

    def list_all_groups(self):
        groups = cloudpassage.ServerGroup(self.session)
        return groups.list_all()

    def generate_server_report(self, target):
        server_id = self.get_id_for_server_target(target)
        structure = {}
        if server_id is not None:
            server_obj = cloudpassage.Server(self.session)
            structure["facts"] = server_obj.describe(server_id)
            structure["events"] = self.get_events_by_server(server_id)
            structure["issues"] = self.get_issues_by_server(server_id)
        return structure

    def generate_group_report(self, target):
        group_id = self.get_id_for_group_target(target)
        structure = {}
        if group_id is not None:
            group_obj = cloudpassage.ServerGroup(self.session)
            structure["facts"] = group_obj.describe(group_id)
            structure["policies"] = self.get_group_policies(structure["facts"])
        return structure

    def get_group_policies(self, grp_struct):
        retval = []
        firewall_keys = ["firewall_policy_id", "windows_firewall_policy_id"]
        csm_keys = ["policy_ids", "windows_policy_ids"]
        fim_keys = ["fim_policy_ids", "windows_fim_policy_ids"]
        lids_keys = ["lids_policy_ids"]
        print("Getting meta for FW policies")
        for fwp in firewall_keys:
            retval.append(self.get_policy_metadata(grp_struct[fwp], "FW"))
        print("Getting meta for CSM policies")
        for csm in csm_keys:
            retval.append(self.get_policy_list(grp_struct[csm], "CSM"))
        print("Getting meta for FIM policies")
        for fim in fim_keys:
            retval.append(self.get_policy_list(grp_struct[fim], "FIM"))
        print("Getting meta for LIDS policies")
        for lids in lids_keys:
            retval.append(self.get_policy_list(grp_struct[lids], "LIDS"))
        print("Gathered all policy metadata successfully")
        return retval

    def get_policy_list(self, policy_ids, policy_type):
        retval = []
        for policy_id in policy_ids:
            retval.append(self.get_policy_metadata(policy_id, policy_type))
        return retval

    def get_policy_metadata(self, policy_id, policy_type):
        p_ref = {"FW": " Firewall",
                 "CSM": "Configuration",
                 "FIM": "File Integrity Monitoring",
                 "LIDS": "Log-Based IDS"}
        if policy_id is None:
            return ""
        elif policy_type == "FIM":
            pol = cloudpassage.FimPolicy(self.session)
        elif policy_type == "CSM":
            pol = cloudpassage.ConfigurationPolicy(self.session)
        elif policy_type == "FW":
            pol = cloudpassage.FirewallPolicy(self.session)
        elif policy_type == "LIDS":
            pol = cloudpassage.LidsPolicy(self.session)
        else:
            return ""
        retval = pol.describe(policy_id)
        return retval

    def get_id_for_group_target(self, target):
        """Attempts to get group_id using arg:target as group_name, then id"""
        group = cloudpassage.ServerGroup(self.session)
        orig_result = group.list_all()
        result = []
        for x in orig_result:
            if x["name"] == target:
                result.append(x)
        if len(result) > 0:
            return result[0]["id"]
        else:
            try:
                result = group.describe(target)["id"]
            except cloudpassage.CloudPassageResourceExistence:
                result = None
            except KeyError:
                result = None
        return result

    def get_id_for_server_target(self, target):
        """Attempts to get server_id using arg:target as hostname, then id"""
        server = cloudpassage.Server(self.session)
        result = server.list_all(hostname=target)
        if len(result) > 0:
            return result[0]["id"]
        else:
            try:
                result = server.describe(target)["id"]
            except:
                print("Not a hostnamename or server ID: " + target)
                result = None
        return result

    def get_events_by_server(self, server_id, number_of_events=20):
        """Return events for a server.  Defaults to last 100."""
        events = []
        starting = util.iso8601_yesterday()
        search_params = {"server_id": server_id, "sort_by": "created_at.desc"}
        h_e = haloevents.HaloEvents(self.halo_api_key, self.halo_api_secret,
                                    start_timestamp=starting,
                                    search_params=search_params)
        for event in h_e:
            events.append(event)
            if len(events) >= number_of_events:
                break
        return events

    def get_issues_by_server(self, server_id):
        pagination_key = 'issues'
        url = '/v2/issues'
        params = {'agent_id': server_id}
        hh = cloudpassage.HttpHelper(self.session)
        issues = hh.get_paginated(url, pagination_key, 5, params=params)
        return issues

    def list_servers_in_group(self, target):
        """Return a list of servers in group after sending through formatter"""
        group = cloudpassage.ServerGroup(self.session)
        group_id = self.get_id_for_group_target(target)
        if group_id is None:
            return group_id
        else:
            return group.list_members(group_id)
