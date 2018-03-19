import cloudpassage
import os
from utility import Utility as util
from formatter import Formatter as fmt


class Halo(object):
    def __init__(self):
        self.halo_api_key = os.getenv("HALO_API_KEY")
        self.halo_api_secret = os.getenv("HALO_API_SECRET_KEY")
        self.halo_api_key_rw = os.getenv("HALO_API_KEY_RW")
        self.halo_api_secret_rw = os.getenv("HALO_API_SECRET_KEY_RW")
        self.session = cloudpassage.HaloSession(self.halo_api_key,
                                                self.halo_api_secret)
        self.rw_session = cloudpassage.HaloSession(self.halo_api_key_rw,
                                                   self.halo_api_secret_rw)

    def list_all_servers_formatted(self):
        servers = cloudpassage.Server(self.session)
        return fmt.format_list(servers.list_all(), "server_facts")

    def list_all_groups_formatted(self):
        groups = cloudpassage.ServerGroup(self.session)
        return fmt.format_list(groups.list_all(), "group_facts")

    def generate_server_report_formatted(self, target):
        server_id = self.get_id_for_server_target(target)
        result = ""
        if server_id is not None:
            print("ServerReport: Starting report for %s" % server_id)
            server_obj = cloudpassage.Server(self.session)
            print("ServerReport: Getting server facts")
            facts = self.flatten_ec2(server_obj.describe(server_id))
            if "aws_ec2" in facts:
                result = fmt.format_item(facts, "server_ec2")
            else:
                result = fmt.format_item(facts, "server_facts")
            print("ServerReport: Getting server issues")
            result += fmt.format_list(self.get_issues_by_server(server_id),
                                      "issue")
            print("ServerReport: Getting server events")
            result += fmt.format_list(self.get_events_by_server(server_id),
                                      "event")
        else:
            result = "Unable to find server %s" % target
        return result

    def generate_group_report_formatted(self, target):
        group_id = self.get_id_for_group_target(target)
        result = ""
        if group_id is not None:
            group_obj = cloudpassage.ServerGroup(self.session)
            grp_struct = group_obj.describe(group_id)
            result = fmt.format_item(grp_struct, "group_facts")
            result += self.get_group_policies(grp_struct)
        else:
            result = "Unable to find group %s" % target
        return result

    def get_group_policies(self, grp_struct):
        retval = ""
        firewall_keys = ["firewall_policy_id", "windows_firewall_policy_id"]
        csm_keys = ["policy_ids", "windows_policy_ids"]
        fim_keys = ["fim_policy_ids", "windows_fim_policy_ids"]
        lids_keys = ["lids_policy_ids"]
        print("Getting meta for FW policies")
        for fwp in firewall_keys:
            retval += self.get_policy_metadata(grp_struct[fwp], "FW")
        print("Getting meta for CSM policies")
        for csm in csm_keys:
            retval += self.get_policy_list(grp_struct[csm], "CSM")
        print("Getting meta for FIM policies")
        for fim in fim_keys:
            retval += self.get_policy_list(grp_struct[fim], "FIM")
        print("Getting meta for LIDS policies")
        for lids in lids_keys:
            retval += self.get_policy_list(grp_struct[lids], "LIDS")
        print("Gathered all policy metadata successfully")
        return retval

    def get_policy_list(self, policy_ids, policy_type):
        retval = ""
        for policy_id in policy_ids:
            retval += self.get_policy_metadata(policy_id, policy_type)
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
        retval = fmt.policy_meta(pol.describe(policy_id), p_ref[policy_type])
        return retval

    def get_id_for_group_target(self, target):
        """Attempts to get group_id using arg:target as group_name, then id"""
        group = cloudpassage.ServerGroup(self.session)
        orig_result = group.list_all()
        result = []
        for x in orig_result:
            if x["name"] == target:
                result.append(x)
        if len(result) > 1:
            return fmt.format_list(result, "group_facts")
        elif not result:
            try:
                result.append(group.describe(target))
            except cloudpassage.CloudPassageResourceExistence:
                result = None
        try:
            return result[0]["id"]
        except:
            result = None
        return result

    def get_id_for_server_target(self, target):
        """Attempts to get server_id using arg:target as hostname, then id"""
        server = cloudpassage.Server(self.session)
        result = server.list_all(hostname=target)
        if len(result) > 1:
            return fmt.format_list(result, "server_facts")
        elif not result:
            try:
                result = [server.describe(target)]
            except cloudpassage.CloudPassageResourceExistence:
                result = None

        try:
            return result[0]["id"]
        except:
            result = None
        return result

    def get_events_by_server(self, server_id, number_of_events=20):
        """Return events for a server, Goes back up to a week to find 20."""
        events = []
        h_h = cloudpassage.HttpHelper(self.session)
        starting = util.iso8601_one_week_ago()
        search_params = {"server_id": server_id,
                         "sort_by": "created_at.desc",
                         "since": starting}
        halo_events = h_h.get("/v1/events", params=search_params)["events"]
        for event in halo_events:
            if len(events) >= number_of_events:
                return events
            events.append(event)
        return events

    def get_issues_by_server(self, server_id):
        pagination_key = 'issues'
        url = '/v2/issues'
        params = {'agent_id': server_id}
        hh = cloudpassage.HttpHelper(self.session)
        issues = hh.get_paginated(url, pagination_key, 5, params=params)
        return issues

    def list_servers_in_group_formatted(self, target):
        """Return a list of servers in group after sending through formatter"""
        group = cloudpassage.ServerGroup(self.session)
        group_id = self.get_id_for_group_target(target)

        if group_id is None:
            return group_id
        else:
            try:
                return fmt.format_list(group.list_members(group_id),
                                       "server_facts")
            except:
                message = "Found mulitple server groups with same group name\n"
                return message+group_id

    def get_server_by_cve(self, cve):
        pagination_key = 'servers'
        url = '/v1/servers'
        params = {'cve': cve}
        hh = cloudpassage.HttpHelper(self.session)
        servers = hh.get_paginated(url, pagination_key, 5, params=params)
        message = "Server(s) that contains CVE: %s\n" % cve
        return message+fmt.format_list(servers, "server_facts")

    def move_server(self, server_id, group_id):
        """Silence is golden.  If it doesn't throw an exception, it worked."""
        server_obj = cloudpassage.Server(self.rw_session)
        server_obj.assign_group(server_id, group_id)

    def get_id_for_ip_zone(self, ip_zone_name):
        zone_obj = cloudpassage.FirewallZone(self.session)
        all_zones = zone_obj.list_all()
        for zone in all_zones:
            if zone["name"] == ip_zone_name:
                return zone["id"]
        return None

    def add_ip_to_zone(self, ip_address, zone_name):
        update_zone = {"firewall_zone": {"name": zone_name}}
        zone_obj = cloudpassage.FirewallZone(self.rw_session)
        zone_id = self.get_id_for_ip_zone(zone_name)
        if zone_id is None:
            msg = "Unable to find ID for IP zone %s!\n" % zone_name
            return msg
        else:
            update_zone["firewall_zone"]["id"] = zone_id
        existing_zone = zone_obj.describe(zone_id)
        existing_ips = util.ipaddress_list_from_string(existing_zone["ip_address"])  # NOQA
        if ip_address in existing_ips:
            msg = "IP address %s already in zone %s !\n" % (ip_address,
                                                            zone_name)
        else:
            existing_ips.append(ip_address)
            update_zone["firewall_zone"]["ip_address"] = util.ipaddress_string_from_list(existing_ips)  # NOQA
            zone_obj.update(update_zone)
            msg = "Added IP address %s to zone ID %s\n" % (ip_address,
                                                           zone_name)
        return msg

    def remove_ip_from_zone(self, ip_address, zone_name):
        update_zone = {"firewall_zone": {"name": zone_name}}
        zone_obj = cloudpassage.FirewallZone(self.rw_session)
        zone_id = self.get_id_for_ip_zone(zone_name)
        if zone_id is None:
            msg = "Unable to find ID for IP zone %s!\n" % zone_name
            return msg
        else:
            update_zone["firewall_zone"]["id"] = zone_id
        existing_zone = zone_obj.describe(zone_id)
        existing_ips = util.ipaddress_list_from_string(existing_zone["ip_address"])  # NOQA
        try:
            existing_ips.remove(ip_address)
            update_zone["firewall_zone"]["ip_address"] = util.ipaddress_string_from_list(existing_ips)  # NOQA
            zone_obj.update(update_zone)
            msg = "Removed IP %s from zone %s\n" % (ip_address, zone_name)
        except ValueError:
            msg = "IP %s was not found in zone %s\n" % (ip_address, zone_name)
        return msg

    @classmethod
    def flatten_ec2(cls, server):
        try:
            for k, v in server["aws_ec2"].items():
                server[k] = v
            if "ec2_security_groups" in server:
                conjoined = " ,".join(server["ec2_security_groups"])
                server["ec2_security_groups"] = conjoined
            return server
        except:
            return server
