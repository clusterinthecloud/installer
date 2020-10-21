from __future__ import print_function

import os
import stat
import sys
from subprocess import check_call
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve
from zipfile import ZipFile

def main():
    csp = sys.argv[1]

    tf_repo_zip, _ = urlretrieve("https://github.com/clusterinthecloud/terraform/archive/master.zip")
    ZipFile(tf_repo_zip).extractall()

    if sys.platform.startswith("linux"):
        tf_platform = "linux_amd64"
    elif sys.platform == "darwin":
        tf_platform = "darwin_amd64"
    elif sys.platform == "win32":
        raise NotImplementedError("Windows is not supported at the mooment")
    else:
        raise NotImplementedError("Platform is not supported")

    tf_version = "0.12.29"
    tf_template = "https://releases.hashicorp.com/terraform/{v}/terraform_{v}_{p}.zip"
    tf_url = tf_template.format(v=tf_version, p=tf_platform)
    tf_zip, _ = urlretrieve(tf_url)
    ZipFile(tf_zip).extractall()
    os.chmod("terraform", stat.S_IRWXU)

    check_call(["./terraform", "init", "terraform-master/{}".format(csp)])
    check_call(["./terraform", "validate", "terraform-master/{}".format(csp)])


if __name__ == "__main__":
    main()
