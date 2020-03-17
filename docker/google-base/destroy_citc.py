
import argparse
import sys
import json
import os
import shlex
import subprocess

default_zone = "europe-west2-c"

parser = argparse.ArgumentParser()

parser.add_argument("--host",
                    help="The hostname or IP address of the login node "
                         "of the cluster you want to destroy")
parser.add_argument("--zone", help=f"Set the zone in which the cluster will "
                                   f"be created (default {default_zone})")
parser.add_argument("--project", help="Set the project in which the cluster "
                                      "will be created")
parser.add_argument("--name", help="The name of the cluster")
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
    cluster_name = None
    project = None
    zone = None

    if args.host:
        hostname = str(args.host)

    if args.project:
        project = str(args.project)

    if args.zone:
        zone = str(args.zone)

    if args.name:
        cluster_name = str(args.name)

    if args.json:
        try:
            with open(args.json, "r") as FILE:
                data = json.load(FILE)
        except Exception as e:
            print(f"Failed to read parameters from json file "
                  f"'{args.json}': {e}")
            sys.exit(-1)

        if "host" in data:
            hostname = str(data["host"])

        if "project" in data:
            project = str(data["project"])

        if "zone" in data:
            zone = str(data["zone"])

        if "name" in data:
            cluster_name = str(data["name"])

    while not hostname:
        hostname = input("What is the hostname or IP address of the login "
                         "node? ")

    while not cluster_name:
        cluster_name = input("What is the name of the CitC cluster? ")

    while not project:
        project = input("Which google project was the cluster "
                        "created in? ")

    while not zone:
        zone = input(f"What zone was the cluster created in "
                     f"[{default_zone}]? ")

        if not zone:
            zone = default_zone


    print(f"\nDestroying the CitC with login node {hostname}")

    if dry:
        print("*** DRY RUN ***\n\n")

    if not has_completed("gcloud_set_project"):
        run_command(f"gcloud config set project {project}")

    if not has_completed("gcloud_login"):
        run_command("gcloud auth login")

    if not has_completed("download_terraform"):
        scp_options = f"--strict-host-key-checking=no --quiet --zone={zone}"

        run_command(f"gcloud config set project {project}")
        run_command(f"gcloud compute scp {scp_options} "
                    f"provisioner@mgmt-{cluster_name}:terraform.tgz "
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

    if not has_completed("gcloud_enable_services"):
        run_command(f"gcloud services enable compute.googleapis.com "
                                        f"iam.googleapis.com "
                                        f"cloudresourcemanager.googleapis.com "
                                        f"file.googleapis.com")

    if not has_completed("terraform_destroy"):
        if not dry:
            os.chdir("citc-terraform")
            print(os.getcwd())

        run_command("terraform init google")
        run_command("terraform destroy -auto-approve google")

    if not has_completed("remove_service_account"):
        citc_name = f"citc-admin-{cluster_name}"
        run_command(f"gcloud iam service-accounts delete --quiet "
                    f"{citc_name}@{project}.iam.gserviceaccount.com")

    if not has_completed("remove_images"):
        citc_family_name = f"citc-slurm-compute-{cluster_name}"
        get_images = f"gcloud compute images list --format \"table[no-heading](name)\" --filter \"family={citc_family_name}\""
                
        args = shlex.split(get_images)
        p1 = subprocess.Popen(args, stdout=subprocess.PIPE)    
        delete_images = f"xargs gcloud compute images delete -q" 
        args = shlex.split(delete_images)
        p2 = subprocess.Popen(args, stdin=p1.stdout, stdout=subprocess.PIPE)
        p1.stdout.close()
        print(f"[EXECUTE] {get_images} | {delete_images}")
        output = p2.communicate()[0]
            
    has_completed("everything")

    print("\n\nYour Cluster-in-the-Cloud has now been deleted :-(\n")

try:
    run_everything(args)
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(-1)

print("{\"status\":\"0\"}")
