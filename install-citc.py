from __future__ import print_function, unicode_literals

import argparse
import os
import os.path
import stat
import subprocess
import sys
import shutil
import time
from subprocess import call, check_call, check_output, CalledProcessError
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve
from zipfile import ZipFile

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csp", choices=["aws"], help="Which cloud provider to install into")
    parser.add_argument("--dry-run", help="Perform a dry run", action="store_true")
    parser.add_argument("--region", help="AWS region")
    parser.add_argument("--availability_zone", help="AWS availability zone")
    parser.add_argument("--profile", help="AWS credentials profile")
    parser.add_argument("--terraform-repo", default="clusterinthecloud/terraform", help="CitC Terraform GitHub project repo to use")
    parser.add_argument("--terraform-branch", default="tf_0_13_aws", help="CitC Terraform branch to use")
    parser.add_argument("--ansible-repo", help="CitC Ansible repo to use")
    parser.add_argument("--ansible-branch", help="CitC Ansible branch to use")
    args = parser.parse_args()

    print("Installing Cluster in the Cloud on AWS")

    try:
        check_command = ["aws", "--dry-run", "ec2", "describe-images"]
        if args.profile:
            check_command.extend(["--profile", args.profile])
        if args.region:
            check_command.extend(["--region", args.region])
        check_output(check_command, stderr=subprocess.STDOUT)
    except CalledProcessError as e:
        if "RequestExpired" in e.output.decode():
            print("AWS credentials have expired:")
        if "DryRunOperation" not in e.output.decode():
            print(e.output.decode())
            exit(1)

    #Download the CitC Terraform repo
    print("Downloading CitC Terraform configuration")
    tf_repo_zip, _ = urlretrieve("https://github.com/{repo}/archive/{branch}.zip".format(repo=args.terraform_repo, branch=args.terraform_branch))
    ZipFile(tf_repo_zip).extractall()
    shutil.rmtree("citc-terraform", ignore_errors=True)
    os.rename("terraform-{branch}".format(branch=args.terraform_branch), "citc-terraform")
    os.chdir("citc-terraform")

    # Download Terraform binary
    if sys.platform.startswith("linux"):
        tf_platform = "linux_amd64"
    elif sys.platform == "darwin":
        tf_platform = "darwin_amd64"
    elif sys.platform == "win32":
        raise NotImplementedError("Windows is not supported at the mooment")
    else:
        raise NotImplementedError("Platform is not supported")
    tf_version = "0.14.0"
    tf_template = "https://releases.hashicorp.com/terraform/{v}/terraform_{v}_{p}.zip"
    tf_url = tf_template.format(v=tf_version, p=tf_platform)
    print("Downloading Terraform binary")
    tf_zip, _ = urlretrieve(tf_url)
    ZipFile(tf_zip).extractall()
    os.chmod("terraform", stat.S_IRWXU)

    # Create key for admin and provisioning
    if not os.path.isfile("citc-key"):
        check_call(["ssh-keygen", "-t", "rsa", "-f", "citc-key", "-N", ""])

    # Intialise Terraform
    check_call(["./terraform", "init", args.csp])
    check_call(["./terraform", "validate", args.csp])

    # Set up the variable file
    config_file(args.csp, args)

    # Create the cluster
    if not args.dry_run:
        check_call(["./terraform", "apply", "-auto-approve", args.csp])

    # Get the outputs
    ip = check_output(["./terraform", "output", "-no-color", "-state=terraform.tfstate", "ManagementPublicIP"]).decode().strip().strip('"')
    cluster_id = check_output(["./terraform", "output", "-no-color", "-state=terraform.tfstate", "cluster_id"]).decode().strip().strip('"')

    os.chdir("..")
    new_dir_name = "citc-terraform-{}".format(cluster_id)
    os.rename("citc-terraform", new_dir_name)

    key_path = "{}/citc-key".format(new_dir_name)

    shutil.rmtree(os.path.join(new_dir_name, ".terraform"))
    tf_zip = shutil.make_archive("citc-terraform", "zip", ".", new_dir_name)
    if not args.dry_run:
        while call(["scp", "-i", key_path, "-o", "StrictHostKeyChecking no", "-o", "IdentitiesOnly=yes", tf_zip, "citc@{}:.".format(ip)]) != 0:
            print("Trying to upload Terraform state...")
            time.sleep(10)
    os.remove(tf_zip)

    print("")
    print("#"*80)
    print("")
    print("The file '{}' will allow you to log into the new cluster".format(key_path))
    print("Make sure you save this key as it is needed to destroy the cluster later.")

    print("The IP address of the cluster is {}".format(ip))
    print("Connect with:")
    print("  ssh -i {ssh_id} citc@{ip}".format(ssh_id=key_path, ip=ip))


def config_file(csp, args):
    with open(os.path.join(csp, "terraform.tfvars.example")) as f:
        config = f.read()

    if csp == "aws":
        config = aws_config_file(config, args)
    else:
        raise NotImplementedError("Other providers are not supported yet")

    if args.ansible_repo:
        config = config + '\nansible_repo = "{}"'.format(args.ansible_repo)
    if args.ansible_branch:
        config = config + '\nansible_branch = "{}"'.format(args.ansible_branch)

    with open("terraform.tfvars", "w") as f:
        f.write(config)


def aws_config_file(config, args):
    config = config.replace("~/.ssh/aws-key", "citc-key")
    with open("citc-key.pub") as pub_key:
        pub_key_text = pub_key.read().strip()
    config = config.replace("admin_public_keys = <<EOF", "admin_public_keys = <<EOF\n" + pub_key_text)
    if args.region:
        config += '\nregion = "{}"'.format(args.region)
    if args.availability_zone:
        config += '\navailability_zone = "{}"'.format(args.availability_zone)
    if args.profile:
        config += '\nprofile = "{}"'.format(args.profile)
    return config


if __name__ == "__main__":
    main()
