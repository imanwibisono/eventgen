#!/usr/bin/env python2
# encoding: utf-8
"""
Continuous Delivery script that automates code deployment from the cut of release branches
"""
import argparse
import os
import sys
import re
import subprocess
import json
import shutil
from github import Github

file_location = os.path.dirname(os.path.realpath(__file__))
splunk_eventgen_location = os.path.normpath(os.path.join(file_location, ".."))
eventgen_external_location = os.path.normpath(os.path.join(splunk_eventgen_location, "..", "eventgen_external"))
eventgen_internal_location = os.path.normpath(os.path.join(splunk_eventgen_location, "..", "eventgen_internal"))
internal_remove_paths = ["Makefile", "Jenkinsfile", "scripts", "documentation/deploy.py", "documentation/node_modules",
                         "documentation/_book", "documentation/CHANGELOG.md"]
splunkbase_url = "https://splunkbase.splunk.com/app/1924/edit/#/hosting"
artifactory_url = ""
internal_git_url = ""
external_git_url = ""

sys.path.insert(0, splunk_eventgen_location)
from splunk_eventgen.__init__ import _set_dev_version, _set_release_version


def execute_command(command, working_dir):
    """

    """
    cwd = os.getcwd()
    os.chdir(working_dir)
    output = os.system(command)
    os.chdir(cwd)
    return output

def create_external_branch(repo_path, new_version):
    """
    Create a new release branch for our external git repository, assuming our current branch is up to date.
    """
    # Change to the directory that holds our .git reference
    branch_status = execute_command("git status", repo_path)
    # Check if current branch is clean / up-to-date | TODO: need to test
    if "nothing to commit, working tree clean" in branch_status:
        execute_command("git checkout -b release/{}".format(new_version), repo_path)


def update_versions(new_version, root_path):
    """
    Update all version references to the new release version
    """
    # update version file
    version_file = os.path.normpath(os.path.join(root_path, "splunk_eventgen/version.json"))
    conf_file = os.path.normpath(os.path.join(root_path, "splunk_eventgen/splunk_app/default/app.conf"))
    with open(version_file, "r") as infile:
        version_json = json.load(infile)
        version_json["version"] = new_version
    with open(version_file, "w") as outfile:
        json.dump(version_json, outfile)
    # update version and reset build # in app.conf
    with open(conf_file, "r") as infile:
        lines = infile.read()
        lines = re.sub("build = [0-9]*", "build = 1", lines)
        lines = re.sub("version = [0-9.dev]*", "version = {}".format(new_version), lines)
    with open(conf_file, "w") as outfile:
        outfile.write(lines)


def prepare_internal_release(new_version, artifactory, pip, container):
    """
    Prepare documentation for release and publish to specified internal sources
    """
    # AFTER CUTTING NEW release/x.x.x BRANCH:
    update_versions(new_version, eventgen_internal_location)
    # TODO: push to bitbucket repository
    #p = subprocess.Popen(["make", "push_release_egg"], cwd=eventgen_internal_location)
    #p = subprocess.Popen(["make", "push_image_production"], cwd=eventgen_internal_location)
    # TODO: write a release notes and distribute to productsall + eng (commit messages? manual?)
    # handle publishing methods
    if artifactory:
        pass
    if pip:
        pass
    if container:
        pass
    # update latest develop version.json with next dev version
    update_versions(new_version+'.dev0', eventgen_internal_location)


def prepare_external_release(new_version, splunkbase, external_github):
    """
    Remove all sensitive Splunk information from codebase and publish to specified external sources
    """
    # AFTER CUTTING NEW release/x.x.x_open_source BRANCH
    update_versions(new_version, eventgen_external_location)
    remove_internal_references(new_version)
    # handle publishing methods
    if splunkbase:
        pass
    if external_github:
        pass


def remove_internal_references(new_version):
    """
    Remove all files / in-line references to Splunk credentials and other sensitive information
    """
    # Checkout new branch for external release
    #g = github.Github(ACCESS_TOKEN)
    p = subprocess.call(["make", "clean"], cwd=eventgen_external_location)
    # TODO: remove splunk link inside setup.py
    for relative_path in internal_remove_paths:
        path = os.path.normpath(os.path.join(eventgen_external_location, relative_path))
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
    # TODO: remove below code block from eventgen_core.py in _setup_loggers method:
    # try:
    #   hec_info = self.get_hec_info_from_conf()
    #   self.hec_logging_handler = splunk_hec_logging_handler.SplunkHECHandler(targetserver=hec_info[0], hec_token=hec_info[1])
    #   logging.getLogger().addHandler(self.hec_logging_handler)
    # except Exception as e:
    #    self.logger.exception(e)


def push_pypi(args):
    print "Pushing PyPI..."
    push = subprocess.Popen(["python", "setup.py", "sdist", "upload", "-r", "production"], cwd=splunk_eventgen_location)
    push.wait()


def parse():
    parser = argparse.ArgumentParser(prog="Eventgen Continuous Deployment",
                                     description="Build and upload pip or Docker images")
    subparsers = parser.add_subparsers(title="package_type",
                                       help="please specify which package type to build or deploy", dest="subcommand")
    parser.add_argument("--push", default=False, action="store_true",
                        help="Pypi pushes to production, Container pushes to branch path unless --production flag"
                             "passed, then versioned Eventgen created")
    parser.add_argument("--dev", default=False, action="store_true", help="specify the package if its dev")
    parser.add_argument("--release", default=False, action="store_true", help="specify the package if its release")
    parser.add_argument("--pdf", default=False, action="store_true", help="Generate a pdf from the documentation")

    # internal: .spl (app), pip module, container
    parser.add_argument("--artifactory", "--af", default=False, action="store_true",
                        help="Publish eventgen app to Splunk internal Artifactory as .spl file")
    parser.add_argument("--pip", default=False, action="store_true",
                        help="Publish version update to internal eventgen pip module")
    parser.add_argument("--container", "--ct", default=False, action="store_true",
                        help="Publish new container to internal")

    # external: splunkbase, github
    parser.add_argument("--splunkbase", "--sb", default=False, action="store_true",
                        help="Publish eventgen as an app to external/public splunkbase")
    parser.add_argument("--external-github", "--gh", default=False, action="store_true",
                        help="Publish release version to external/public Github repository")
    parser.add_argument("--version", type=str, default=None, required=True,
                        help="specify version of new release")

    ## Adding Pypi Module subparser
    pypi_subparser = subparsers.add_parser("pypi", help="Build/deploy pypi module to production")
    return parser.parse_args()


def main():
    # Parse out the options, and execute for "help"
    args = parse()
    # Inject correct ansible version into args
    if args.dev:
        _set_dev_version()
    if args.release:
        _set_release_version()
    if args.push:
        push_pypi(args)
    # Copy files to new directories for editing
    if os.path.exists(eventgen_external_location):
        shutil.rmtree(eventgen_external_location)
    shutil.copytree(splunk_eventgen_location, eventgen_external_location)
    if os.path.exists(eventgen_internal_location):
        shutil.rmtree(eventgen_internal_location)
    shutil.copytree(splunk_eventgen_location, eventgen_internal_location)
    # Prepare for releases based on command-line arguments
    prepare_internal_release(args.version, args.artifactory, args.pip, args.container)
    prepare_external_release(args.version, args.splunkbase, args.external_github)


if __name__ == "__main__":
    main()
