
import argparse
import sys
import petname
import json
import os
import shlex
import subprocess

default_zone = "europe-west2-c"
default_shape = "n1-standard-1"
default_branch = "master"

parser = argparse.ArgumentParser()

parser.add_argument("--dry-run", help="Perform a dry run",
                                 action="store_true")
parser.add_argument("--json", help="Provide a JSON file containing input "
                                   "parameters")
parser.add_argument("--zone", help=f"Set the zone in which the cluster will "
                                   f"be created (default {default_zone})")
parser.add_argument("--project", help="Set the project in which the cluster "
                                      "will be created")
parser.add_argument("--key", help="Your public SSH key (either the key, file "
                                  "containing the key, or URL containing "
                                  "the key)")
parser.add_argument("--shape", help=f"The shape used for the management "
                                    f"node (default {default_shape})")

parser.add_argument("--branch", help=f"The branch used for CitC "
                                     f"(default {default_branch})")

parser.add_argument("--ansible-branch", help="The ansible branch to use")

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
    """Function that runs everything in the script"""
    project = None
    zone = None
    user_pubkey = None
    login_shape = None
    cluster_name = None
    branch = None
    ansible_branch = None

    checkpoint_file = "checkpoint_input.json"

    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r") as FILE:
                data = json.load(FILE)

            zone = str(data["zone"])
            project = str(data["project"])
            user_pubkey = str(data["pubkey"])
            login_shape = str(data["shape"])
            cluster_name = str(data["name"])

            if "branch" in data:
                branch = str(data["branch"])

            if "ansible_branch" in data:
                ansible_branch = str(data["ansible_branch"])
        except Exception as e:
            print(f"[ERROR] Error reading checkpoint file: {e}")
            print(f"[ERROR] Remove {checkpoint_file}")
            sys.exit(-1)

    elif args.json:
        try:
            with open(args.json, "r") as FILE:
                data = json.load(FILE)
        except Exception as e:
            print(f"Failed to read parameters from json file "
                  f"'{args.json}': {e}")
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

        if "branch" in data:
            branch = str(data["branch"])
        else:
            branch = default_branch

        if "ansible_branch" in data:
            ansible_branch = str(data["ansible_branch"])
    else:
        if args.zone:
            zone = str(args.zone)

        if args.project:
            project = str(args.project)

        if args.key:
            user_pubkey = str(args.key)

        if args.shape:
            login_shape = str(args.shape)

        if args.branch:
            branch = str(args.branch)

        if args.ansible_branch:
            ansible_branch = str(args.ansible_branch)

    if "CLOUDSDK_CONFIG" in os.environ:
        project = subprocess.run(["gcloud", "config", "get-value", "core/project"], capture_output=True).stdout.decode().strip()
        if project == "(unset)":
            project = None
        zone = subprocess.run(["gcloud", "config", "get-value", "compute/zone"], capture_output=True).stdout.decode().strip()
        if zone == "(unset)":
            zone = None

    while not project:
        project = input("Which google project should the cluster be "
                        "created in? ")

    while not zone:
        zone = input(f"Which zone should the cluster run in "
                     f"[{default_zone}]? ")

        if not zone:
            zone = default_zone

    while not login_shape:
        login_shape = input(f"What shape should be used for the login node "
                            f"[{default_shape}]? ")

        if not login_shape:
            login_shape = default_shape

    while not user_pubkey:
        user_pubkey = input("Please copy here you public SSH key: ")

    while not branch:
        branch = input(f"Which branch should be used of CitC "
                       f"[{default_branch}]? ")

        if not branch:
            branch = default_branch

    user_keyfile = os.path.expanduser(user_pubkey)

    if user_pubkey.startswith("http"):
        import urllib.request
        s = urllib.request.urlopen(user_pubkey).read().decode()
        user_pubkey = str(s)

    elif not user_keyfile.startswith("ssh"):
        if os.path.exists(user_keyfile):
            user_pubkey = open(user_keyfile, "r").readline().strip()
        else:
            print(f"[ERROR] Unable to open keyfile {user_keyfile}")
            sys.exit(-1)

    if not cluster_name:
        cluster_name = petname.generate()

    # save the checkpoint input - need to generate the cluster name
    if not os.path.exists(checkpoint_file):
        with open(checkpoint_file, "w") as FILE:
            data = {"zone": zone,
                    "project": project,
                    "pubkey": user_pubkey,
                    "shape": login_shape,
                    "name": cluster_name,
                    "branch": branch}

            if ansible_branch:
                data["ansible_branch"] = ansible_branch

            FILE.write(json.dumps(data))

    region = "-".join(zone.split("-")[0:-1])

    print(f"\nCreating a Cluster-in-the-Cloud called {cluster_name}")
    print(f"This will be created in the project {project}")
    print(f"The cluster will be created in the region {region}")
    print(f"The cluster will be created in the zone {zone}")
    print(f"The login node will be of shape {login_shape}\n\n")

    if dry:
        print("*** DRY RUN ***\n\n")

    if os.path.exists("citc-terraform"):
        if not dry:
            os.chdir("citc-terraform")
            print(os.getcwd())

        run_command("git pull")
    else:
        run_command(f"git clone --branch {branch} "
                    f"https://github.com/ACRC/citc-terraform.git")

        if not dry:
            os.chdir("citc-terraform")
            print(os.getcwd())

    if not has_completed("gcloud_set_project"):
        run_command(f"gcloud config set project {project}")

    if not subprocess.run(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"], capture_output=True).stdout.decode().strip():
        if not has_completed("gcloud_login"):
            run_command("gcloud auth login")

    if not has_completed("gcloud_enable_services"):
        run_command(f"gcloud services enable compute.googleapis.com "
                                        f"iam.googleapis.com "
                                        f"cloudresourcemanager.googleapis.com "
                                        f"file.googleapis.com")

    citc_name = f"citc-admin-{cluster_name}"

    if not has_completed("gcloud_add_account"):
        # Create an account to run terraform - this shows that the user
        # has permission to run the subsequent steps. If these fail, then
        # we can send back a meaningful error message
        run_command(f"gcloud iam service-accounts create {citc_name} "
                                        f"--display-name {citc_name}")

        run_command(f"gcloud projects add-iam-policy-binding {project} "
                    f"--member serviceAccount:"
                    f"{citc_name}@{project}.iam.gserviceaccount.com "
                    "--role='roles/editor'")

        run_command(f"gcloud projects add-iam-policy-binding {project} "
                    f"--member serviceAccount:"
                    f"{citc_name}@{project}.iam.gserviceaccount.com "
                    "--role='roles/resourcemanager.projectIamAdmin'")

        run_command("gcloud iam service-accounts keys create "
                    "citc-terraform-credentials.json "
                    f"--iam-account "
                    f"{citc_name}@{project}.iam.gserviceaccount.com")

    ####
    #### Should have everything installed here and have sufficient
    #### permission to run
    ####

    if not has_completed("generate_keys"):
        run_command(f"ssh-keygen -t rsa -f "
                    f"{os.environ['HOME']}/.ssh/citc-google "
                    f"-C provisioner -N \"\"")

    if not has_completed("init_terraform"):
        run_command("terraform init google")

    if not has_completed("create_tfvars"):
        # Now create the tfvars file
        if dry:
            print("\n===Creating the terraform.tfvars===")
            FILE = sys.stdout
        else:
            FILE = open("terraform.tfvars", "w")

        FILE.write("# Google Cloud Platform Information\n")
        FILE.write(f"region           = \"{region}\"\n")
        FILE.write(f"zone             = \"{zone}\"\n")
        FILE.write(f"project          = \"{project}\"\n")
        FILE.write(f"management_shape = \"{login_shape}\"\n")
        FILE.write(f"credentials      = \"citc-terraform-credentials.json\"\n")
        FILE.write(f"private_key_path = \"~/.ssh/citc-google\"\n")
        FILE.write(f"public_key_path  = \"~/.ssh/citc-google.pub\"\n")

        if ansible_branch:
            FILE.write(f"ansible_branch   = \"{ansible_branch}\"\n")

        FILE.write(f"cluster_id       = \"{cluster_name}\"\n")

        if dry:
            print("\n")
        else:
            FILE.close()

    if not has_completed("terraform_validate"):
        run_command("terraform validate google")

    if not has_completed("terraform_plan"):
        run_command("terraform plan google")

    if not has_completed("terraform_apply"):
        run_command("terraform apply -auto-approve google")

    cmd = "terraform output -no-color -state=terraform.tfstate " \
          "ManagementPublicIP"

    if dry:
        print(f"[DRY-RUN] {cmd}")
        cluster_ip = "192.168.0.1"
    else:
        print(f"[EXECUTE] {cmd}")
        try:
            args = shlex.split(cmd)
            p = subprocess.run(args, capture_output=True)
            cluster_ip = p.stdout.decode("utf-8").strip()
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(-1)

    if not has_completed("save_pubkey"):
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

    scp_options = "-o StrictHostKeyChecking=no -i ~/.ssh/citc-google"

    if not has_completed("upload_pubkey"):
        run_command(f"scp {scp_options} citc-admin.pub "
                    f"provisioner@{cluster_ip}:")

    if not has_completed("upload_terraform_files"):
        if not dry:
            os.chdir("..")
            print(os.getcwd())

        run_command("tar -zcvf terraform.tgz .ssh "
                    "citc-terraform "
                    "checkpoint_input.json")
        run_command(f"scp {scp_options} terraform.tgz "
                    f"provisioner@{cluster_ip}:")

    print("\n\nYour Cluster-in-the-Cloud has now been created :-)")
    print("Proceed to the next stage. Connect to the cluster")
    print(f"by running 'ssh citc@{cluster_ip}'\n")

    has_completed("everything")

    return cluster_ip

try:
    cluster_ip = run_everything(args)
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(-1)

print("{\"status\":\"0\", \"cluster_ip\":\"%s\"}" % cluster_ip)
