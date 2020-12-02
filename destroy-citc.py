#! /usr/bin/env python

from __future__ import print_function, unicode_literals

import argparse
import os
import os.path
import stat
import sys
import shutil
from subprocess import check_call, check_output, CalledProcessError
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

    tf_zip_filename = "citc-terraform.zip"
    check_call(["scp", "-i", args.key, "citc@{}:{}".format(args.ip, tf_zip_filename), "."])
    tf_zip = ZipFile(tf_zip_filename)
    dir_name = tf_zip.namelist()[0]
    tf_zip.extractall()

    # Shut down any running compute nodes and delete associated DNS entries
    if not args.dry_run:
        try:
            check_call(["ssh", "-i", args.key, "citc@{}".format(args.ip), "/usr/local/bin/kill_all_nodes --force"])
        except CalledProcessError:
            print("/usr/local/bin/kill_all_nodes failed to run. You may have lingering compute nodes. You must kill these manually.")

    os.chdir(dir_name)

    os.chmod("terraform", stat.S_IRWXU)
    check_call(["./terraform", "init", args.csp])

    if not args.dry_run:
        try:
            check_call(["./terraform", "destroy", "-auto-approve", args.csp])
        except CalledProcessError:
            print("Terraform destroy failed. Try again with:")
            print("  cd {}".format(dir_name))
            print("  ./terraform destroy {}".format(args.csp))
            print("You may need to manually clean up any remaining running instances or DNS entries")


if __name__ == "__main__":
    main()
