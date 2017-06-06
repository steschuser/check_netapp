#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

from __future__ import print_function
import sys
import argparse
import getpass
import time
import pprint
import re
from xml.sax import saxutils
import signal
import traceback

PATH_TO_NETAPP_SDK = "/opt/NetApp/python"

# No need to edit anything beyond this point

# Import Modules
sys.path.append(PATH_TO_NETAPP_SDK)
# Try to import the NetApp Modules
try:
    import NaServer
    from NaElement import NaElement
except ImportError, e:
    print ("NetApp SDK not found")
    print (e)
    sys.exit(-1)


def timeout_handler(signum, frame):
    print('Timeout')
    signal.alarm(0)
    sys.exit(3)


def invoke_api(s, api, api_args):
    out = s.invoke(api, *api_args)
    if out.results_status() != 'passed':
        raise Exception(out.results_reason())
    return out


# Invoke CLI is unsued, left in if support needs to be added
def invoke_cli(s, cli_args):
    """
    Call the unsupported/undocumented system-cli API.
    cli_args, a list of commands, would represent the command line
    if executing in the CLI.
    Return the NaElement result of executing the command.
    """
    args = NaElement('args')
    for arg in cli_args:
        args.child_add(NaElement('arg', arg))
    cli = NaElement('system-cli')
    cli.child_add(args)
    out = s.invoke_elem(cli)
    if out.results_status() != 'passed':
        raise Exception(out.results_reason())
    return out


def check_result(cmd_args, result):
    retcode = 0
    retstr = ""
    filter_result = [x for x in result if x[0] not in cmd_args.exclude]
    try:
        # if any(x for x in result if int(x[1]) > cmd_args.warning and int(x[1]) < cmd_args.critical):
        warnings = ["%s: %s%% in use" % (x[0], x[1]) for x in filter_result if int(x[1]) > cmd_args.warning and int(x[1]) < cmd_args.critical]
        if len(warnings) > 0:
            retstr += "WARNING %s\n" % ("\n".join(warnings))
            retcode = 1

        # if any(x for x in result if int(x[1]) >= cmd_args.critical):
        criticals = ["%s: %s%% in use" % (x[0], x[1]) for x in filter_result if int(x[1]) >= cmd_args.critical]
        if len(criticals) > 0:
            retstr += "CRITICAL %s\n" % ("\n".join(criticals))
            retcode = 2

        if retcode == 0:
            retstr = "OK"

    except ValueError:
        print ("Unexpected result: %s=%s" % (x[0], x[1]))
        sys.exit(3)

    if cmd_args.verbose:
            ok = ["%s: %s%% in use" % (x[0], x[1]) for x in result]
            retstr = "%s \n%s" % (retstr, "\n".join(ok))

    if cmd_args.perfdata:
        perflist = ["'%s'=%s%%" % (x[0], x[1]) for x in result]
        perfstring = " ".join(perflist)
        perfstring = " | %s" % perfstring
        retstr = "%s%s" % (retstr, perfstring)

    return (retstr, retcode)


def get_cluster_health(s, cmd_args):
    out = invoke_api(s, "cluster-peer-health-info-get-iter", [])
    print (out)
    print (out.sprintf())
    return ("Ok", 0)


def list_diagnosis(s, cmd_args):
    out = invoke_api(s, "diagnosis-alert-get-iter", [])
    print (out)
    print (out.sprintf())
    return ("Ok", 0)


def list_alarms(s, cmd_args):
    out = invoke_api(s, "dashboard-alarm-get-iter", [])
    print (out)
    print (out.sprintf())
    return ("Ok", 0)


def list_aggr(s, cmd_args):
    out = invoke_api(s, "aggr-get-iter", [])
    result = []
    while True:
        aggrs = out.child_get("attributes-list")
        for aggr in aggrs.children_get():
            if aggr.child_get("aggr-space-attributes"):
                result.append((aggr.child_get_string("aggregate-name"), aggr.child_get("aggr-space-attributes").child_get_string("physical-used-percent")))
        try:
            next_tag = out.child_get_string("next-tag")
            next_tag = saxutils.escape(next_tag)
        except AttributeError:
            break
        out = invoke_api(s, "aggr-get-iter", ["tag", next_tag])
    return check_result(cmd_args, result)


def list_vol(s, cmd_args):
    out = invoke_api(s, "volume-get-iter", [])
    result = []
    while True:
        volumes = out.child_get("attributes-list")
        if volumes is None:
            break
        # print(volumes.sprintf())
        for volume in volumes.children_get():
            if volume.child_get("volume-space-attributes"):
                result.append((volume.child_get("volume-id-attributes").child_get_string("name"), volume.child_get("volume-space-attributes").child_get_string("physical-used-percent")))
        try:
            next_tag = out.child_get_string("next-tag")
            next_tag = saxutils.escape(next_tag)
        except AttributeError:
            break
        out = invoke_api(s, "volume-get-iter", ["tag", next_tag])
    return check_result(cmd_args, result)

API_MODE = {"CLUSTER": invoke_api}
TRANSPORTS = ["HTTP", "HTTPS"]
SERVER_TYPE = ["FILER"]


def main(args=None):
    """The main routine."""
    if args is None:
        args = sys.argv[1:]

    # Netapp Defaults
    transport_type = "HTTPS"
    server_type = "Filer"
    api_mode = "CLUSTER"
    major_version = 1
    minor_version = 1

    COMMANDS = {"aggr": list_aggr, "vol": list_vol, "cluster_health": get_cluster_health, "netapp_alarms": list_alarms, "diagnose": list_diagnosis}

    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument(dest="hostname", help="netapp hostname")
    argp.add_argument(dest="command", help="command to perform, possible commands: %s" % ",".join(COMMANDS.keys()))
    argp.add_argument("--type", dest="server_type", help="server type, default is: %s" % server_type, default=server_type)
    argp.add_argument("--transport", dest="transport_type", help="transport type, default is: %s" % transport_type, default=transport_type)
    argp.add_argument("--mode", dest="mode", help="api mode, default is: %s" % api_mode, default=api_mode)
    argp.add_argument("--username", help="netapp username")
    argp.add_argument("--password", help="netapp password")
    argp.add_argument("--warning", help="warning threshold in percent, default 80", type=int, default=80)
    argp.add_argument("--critical", help="critical threshold in percent, default 90", type=int, default=90)
    argp.add_argument("--timeout", help="timeout in seconds,default 30", type=int, default=30)
    argp.add_argument("--verbose", action="store_true", help="print output")
    argp.add_argument("--perfdata", action="store_true", help="print performance data")
    argp.add_argument("-X", '--exclude', dest="exclude", help="space seperated list of volumes to exclude in check", default=[], nargs='*')
    args = argp.parse_args()

    # Sanity checks
    if args.transport_type.upper() not in TRANSPORTS:
        print ("Invalid Transport")
        print ("possible transports: %s" % ",".join(TRANSPORTS))
        return(3)

    if args.server_type.upper() not in SERVER_TYPE:
        print ("Invalid API Mode")
        return(3)

    if args.mode.upper() not in API_MODE:
        print ("Invalid Server Type")
        return(3)

    if args.command.lower() not in COMMANDS:
        print ("Invalid command")
        print ("possible commands: %s" % ",".join(COMMANDS.keys()))
        return(3)

    # Get User / Pass
    username = args.username if args.username else getpass.getuser()
    password = args.password if args.password else getpass.getpass("Need password for %s on %s: " % (username, args.hostname))

    # Connect to NAS
    s = NaServer.NaServer(args.hostname, major_version, minor_version)
    s.set_server_type(args.server_type)
    s.set_transport_type(args.transport_type)
    s.set_admin_user(username, password)

    # Set Timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(args.timeout)

    # Invoke System Command
    try:
        retval = COMMANDS[args.command](s, args)
    except Exception, e:
        # traceback.print_exc()
        print (e, file=sys.stderr)
        return (3)

    print(retval[0])
    return (retval[1])

if __name__ == "__main__":
    sys.exit(main())
