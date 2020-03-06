
import argparse
import sys
import petname
import os
import shlex
import subprocess

default_zone = "europe-west2-c"
default_shape = "n1-standard-1"

parser = argparse.ArgumentParser()

parser.add_argument("--dry-run", help="Perform a dry run", action="store_true")
parser.add_argument("--json", help="Provide a JSON file containing input parameters")
parser.add_argument("--zone", help=f"Set the zone in which the cluster will be created (default {default_zone})")
parser.add_argument("--project", help="Set the project in which the cluster will be created")
parser.add_argument("--key", help="Your public SSH key (either the key, file containing the key, or URL containing the key")
parser.add_argument("--shape", help=f"The shape used for the management node (default {default_shape})")

args = parser.parse_args()

if args.dry_run:
    dry = True
else:
    dry = False

last_stage = None

def has_completed(stage):
    global last_stage

    filename = f"completed_{stage.replace(" ","_")}.txt"

    if os.path.exists(filename):
        return True

    if last_stage:
        with open(filename, "w") as FILE:
            FILE.write("completed\n")

    last_stage = stage
    return False

def run_command(cmd):
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
    project = None
    zone = None
    user_pubkey = None
    login_shape = None

    if args.json:
        import json
        try:
            with open(args.json, "r") as FILE:
                data = json.load(FILE)
        except Exception as e:
            print(f"Failed to read parameters from json file '{args.json}': {e}")
            sys.exit(-1)

        if "zone" in data:
            zone = str(data["zone"])
        else:
            zone = default_zone

        if "project" in data:
            project = str(data["project"])

        if "pubkey" in data:
            user_pubkey = str(data["pubkey"])

        if "shape" in data:
            login_shape = str(data["shape"])
        else:
            login_shape = default_shape
    else:
        if args.zone:
            zone = str(args.zone)

        if args.project:
            project = str(args.project)

        if args.key:
            user_pubkey = str(args.key)

        if args.shape:
            login_shape = str(args.shape)

    while not project:
        project = input("Which google project should the cluster be created in? ")

    while not zone:
        zone = input(f"Which zone should the cluster run in [{default_zone}]? ")

        if not zone:
            zone = default_zone

    while not login_shape:
        login_shape = input(f"What shape should be used for the login node [{default_shape}]? ")

        if not login_shape:
            login_shape = default_shape

    while not user_pubkey:
        user_pubkey = input("Please copy here you public SSH key: ")

    region = "-".join(zone.split("-")[0:-1])

    cluster_name = petname.generate()

    print(f"\nCreating a Cluster-in-the-Cloud called {cluster_name}")
    print(f"This will be created in the project {project}")
    print(f"The cluster will be created in the region {region}")
    print(f"The cluster will be created in the zone {zone}")

    if dry:
        print("*** DRY RUN ***\n\n")

    if os.path.exists("citc-terraform"):
        if not dry:
            os.chdir("citc-terraform")

        run_command("git pull")
    else:
        run_command("git clone https://github.com/ACRC/citc-terraform.git")

        if not dry:
            os.chdir("citc-terraform")

    run_command("gcloud auth login")

    run_command(f"gcloud config set project {project}")

    run_command(f"gcloud services enable compute.googleapis.com "
                                    f"iam.googleapis.com "
                                    f"cloudresourcemanager.googleapis.com "
                                    f"file.googleapis.com")

    citc_name = f"citc-admin-{cluster_name}"

    # Create an account to run terraform - this shows that the user
    # has permission to run the subsequent steps. If these fail, then
    # we can send back a meaningful error message
    run_command(f"gcloud iam service-accounts create {citc_name} "
                                    f"--display-name {citc_name}")

    run_command(f"gcloud projects add-iam-policy-binding {project} "
                f"--member serviceAccount:{citc_name}@{project}.iam.gserviceaccount.com "
                "--role='roles/editor'")

    run_command(f"gcloud projects add-iam-policy-binding {project} "
                f"--member serviceAccount:{citc_name}@{project}.iam.gserviceaccount.com "
                "--role='roles/resourcemanager.projectIamAdmin'")

    run_command("gcloud iam service-accounts keys create citc-terraform-credentials.json "
                f"--iam-account {citc_name}@{project}.iam.gserviceaccount.com")

    ####
    #### Should have everything installed here and have sufficient permission to run
    ####

    run_command(f"ssh-keygen -t rsa -f {os.environ['HOME']}/.ssh/citc-google -C provisioner -N \"\"")
    run_command("terraform init google")

    # Now create the tfvars file
    if dry:
        print("\n===Creating the terraform.tfvars===")
        FILE = sys.stdout
    else:
        FILE = open("terraform.tfvars", "w")

    FILE.write("# Google Cloud Platform Information\n")
    FILE.write(f"region                              = \"{region}\"\n")
    FILE.write(f"zone                                = \"{zone}\"\n")
    FILE.write(f"project                             = \"{project}\"\n")
    FILE.write("management_shape                    = \"n1-standard-1\"\n")
    FILE.write("credentials                         = \"citc-terraform-credentials.json\"\n")
    FILE.write("private_key_path                    = \"~/.ssh/citc-google\"\n")
    FILE.write("public_key_path                     = \"~/.ssh/citc-google.pub\"\n")
    FILE.write(f"cluster_id                         = \"{cluster_name}\"\n")

    if dry:
        print("\n")
    else:
        FILE.close()

    run_command("terraform validate google")
    run_command("terraform plan google")
    run_command("terraform apply -auto-approve google")


    cmd = "terraform output -no-color -state=terraform.tfstate ManagementPublicIP"

    if dry:
        print(f"[DRY-RUN] {cmd}")
        cluster_ip = "192.168.0.1"
    else:
        print(f"[EXECUTE] {cmd}")
        try:
            args = shlex.split(cmd)
            p = subprocess.Popen(args)
            cluster_ip = p.readlines()[0].strip()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(-1)

    # upload ${USER_PUBKEY} to citc-user .ssh folder
    if dry:
        FILE = sys.stdout
        print("\n===Creating citc-admin.pub===")
    else:
        FILE = open("citc-admin.pub", "w")

    FILE.write(f"{user_pubkey}\n")

    if dry:
        print("\n")
    else:
        FILE.close()

    run_command(f"scp citc-admin.pub provisioner@{cluster_ip}:")
    run_command(f"scp terraform.tfstate.vars provisioner@{cluster_ip}:")

    print("\n\nYour Cluster-in-the-Cloud has now been created :-)")
    print("Proceed to the next stage. Connect to the cluster")
    print(f"by running 'ssh citc@{cluster_ip}'\n")

    return cluster_ip

try:
    cluster_ip = run_everything(args)
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(-1)

print("{\"cluster_ip\":\"%s\"}" % cluster_ip)
