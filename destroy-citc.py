from __future__ import print_function, unicode_literals

import argparse
import os
import os.path
import stat
import sys
import shutil
from subprocess import check_call, check_output
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve
from zipfile import ZipFile

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csp", help="Which cloud provider to install into")
    parser.add_argument("ip", help="The IP address of the cluster's management node")
    parser.add_argument("key", help="Path of the SSH key from cluster creation")
    parser.add_argument("--dry-run", help="Perform a dry run", action="store_true")
    args = parser.parse_args()

    tf_zip = "citc-terraform.zip"
    check_call(["scp", "-i", args.key, "citc@{}:{}".format(args.ip, tf_zip), "."])
    ZipFile(tf_zip).extractall("downloaded-citc-terraform")

    # Shut down any running packer builders
    if not args.dry_run:
        check_call(["ssh", "-i", args.key, "citc@{}".format(args.ip), "/usr/local/bin/kill_packer"])

    # Shut down any running compute nodes and delete associated DNS entries
    if not args.dry_run:
        check_call(["ssh", "-i", args.key, "citc@{}".format(args.ip), "/usr/local/bin/kill_all_nodes"])

    os.chdir("downloaded-citc-terraform")

    check_call(["./terraform", "init", args.csp])

    if not args.dry_run:
        check_call(["./terraform", "destroy", "-auto-approve", args.csp])


if __name__ == "__main__":
    main()
