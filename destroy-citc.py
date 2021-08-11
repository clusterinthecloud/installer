#! /usr/bin/env python

from __future__ import print_function, unicode_literals

import argparse
import os
import os.path
import stat
import tarfile
from subprocess import check_call, CalledProcessError
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve

try:
    # Python 2/3 compatibility
    input = raw_input
except NameError:
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csp", help="Which cloud provider to install into")
    parser.add_argument("ip", help="The IP address of the cluster's management node")
    parser.add_argument("key", help="Path of the SSH key from cluster creation")
    parser.add_argument("--dry-run", help="Perform a dry run", action="store_true")
    args = parser.parse_args()

    # Check that the user really meant it
    if not args.dry_run:
        proceed = input("Are you sure you want to destroy the cluster at {}? [y/N]: ".format(args.ip))
        if proceed.lower() != "y":
            exit(1)

    # Download the Terraform configuration from the cluster
    tf_zip_filename = "citc-terraform.tar.gz"
    print("Downloading the Terraform configuration from {}".format(args.ip))
    check_call(["scp", "-i", args.key, "-o", "IdentitiesOnly=yes", "citc@{}:{}".format(args.ip, tf_zip_filename), "."])
    tf_tar = tarfile.open(tf_zip_filename)
    dir_name = tf_tar.getnames()[0]
    tf_tar.extractall()

    # Shut down any running compute nodes and delete associated DNS entries
    if not args.dry_run:
        try:
            print("Connecting to the cluster to destroy lingering compute nodes...")
            check_call(["ssh", "-i", args.key, "-o", "IdentitiesOnly=yes", "citc@{}".format(args.ip), "/usr/local/bin/kill_all_nodes --force"])
        except CalledProcessError:
            print("/usr/local/bin/kill_all_nodes failed to run. You may have lingering compute nodes. You must kill these manually.")

    os.chdir(dir_name)

    os.chmod("terraform", stat.S_IRWXU)
    check_call(["./terraform", "-chdir={}".format(args.csp), "init"])

    if not args.dry_run:
        try:
            print("Destroying cluster...")
            check_call(["./terraform", "-chdir={}".format(args.csp), "apply", "-destroy", "-auto-approve"])
        except CalledProcessError:
            print("Terraform destroy failed. Try again with:")
            print("  cd {}".format(dir_name))
            print("  ./terraform -chdir={} apply -destroy ".format(args.csp))
            print("You may need to manually clean up any remaining running instances or DNS entries")


if __name__ == "__main__":
    main()
