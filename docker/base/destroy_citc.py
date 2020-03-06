
import argparse
import sys
import json
import os
import shlex
import subprocess

parser = argparse.ArgumentParser()

parser.add_argument("--host",
                    help="The hostname or IP address of the login node "
                         "of the cluster you want to destroy")

parser.add_argument("--dry-run",
                    help="Perform a dry run", action="store_true")

parser.add_argument("--json", help="Provide a JSON file containing input "
                                   "parameters")

args = parser.parse_args()

if args.dry_run:
    dry = True
else:
    dry = False

last_stage = None

def has_completed(stage):
    """Has the stage 'stage' completed yet? Returns True if it has, or else
       False if it hasn't. Checking if 'stage' has completed implies that
       any previous stage must have completed.
    """
    global last_stage

    filename = f'checkpoint_{stage.replace(" ", "_")}.txt'

    if os.path.exists(filename):
        return True

    if last_stage:
        last_filename = f'checkpoint_{last_stage.replace(" ","_")}.txt'
        with open(last_filename, "w") as FILE:
            FILE.write("completed\n")

    last_stage = stage
    return False

def run_command(cmd):
    """Run the passed shell command"""
    if dry:
        print(f"[DRY-RUN] {cmd}")
        return

    print(f"[EXECUTE] {cmd}")

    try:
        args = shlex.split(cmd)
        subprocess.run(args).check_returncode()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(-1)

def run_everything(args):
    hostname = None

    if args.host:
        hostname = str(args.host)

    elif args.json:
        try:
            with open(args.json, "r") as FILE:
                data = json.load(FILE)
        except Exception as e:
            print(f"Failed to read parameters from json file "
                  f"'{args.json}': {e}")
            sys.exit(-1)

        if "host" in data:
            hostname = str(data["host"])

    while not hostname:
        hostname = input("What is the hostname or IP address of the login "
                         "node? ")

    print(f"\nDestroying the CitC with login node {hostname}")

    if dry:
        print("*** DRY RUN ***\n\n")

    if not has_completed("gcloud_login"):
        run_command("gcloud auth login")

    if not has_completed("download_terraform"):
        run_command(f"gcloud compute scp provisioner@{hostname}:terraform.tgz "
                    f"./terraform.tgz")

    if not has_completed("untar_files"):
        run_command("tar -zxvf terraform.tgz")

    if dry:
        cluster_name = "missing_lemur"
        project = "my_project"
    else:
        with open("checkpoint_input.json") as FILE:
            data = json.load(FILE)

        cluster_name = str(data["name"])
        project = str(data["project"])

    print(f"Destroying the cluster called {cluster_name} in project {project}")

    if not has_completed("gcloud_set_project"):
        run_command(f"gcloud config set project {project}")

    if not has_completed("gcloud_enable_services"):
        run_command(f"gcloud services enable compute.googleapis.com "
                                        f"iam.googleapis.com "
                                        f"cloudresourcemanager.googleapis.com "
                                        f"file.googleapis.com")

    if not has_completed("terraform_destroy"):
        run_command("terraform destroy")

    if not has_completed("remove_service_account"):
        citc_name = f"citc-admin-{cluster_name}"
        run_command(f"gcloud iam service-accounts delete "
                    f"{citc_name}@{project}.iam.gserviceaccount.com")

    has_completed("everything")

    print("\n\nYour Cluster-in-the-Cloud has now been deleted :-(")

try:
    run_everything(args)
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(-1)
