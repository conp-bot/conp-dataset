#!/usr/bin/env python
import argparse
import traceback
import os
import json
from git import Repo
from datalad import api


def unlock():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=r"""
        Script which allows to unlock a restricted dataset given the correct token

        Requirements:
        * The token must be passed to the script via the command line
        * Script must be run in the base directory of the dataset
        * File '.conp-zenodo-crawler.json' must exist
        * Dataset git repository must be set on branch 'master'
        """,
    )
    parser.add_argument(
        "token", help="Zenodo access token"
    )
    args = parser.parse_args()
    token = args.token

    repo = Repo()
    annex = repo.git.annex
    if repo.active_branch.name != "master":
        raise Exception("Dataset repository not set to branch 'master'")

    if not os.path.isfile(".conp-zenodo-crawler.json"):
        raise Exception("'.conp-zenodo-crawler.json file not found")

    with open(".conp-zenodo-crawler.json", "r") as f:
        metadata = json.load(f)

    # Ensure correct data
    if not metadata["restricted"]:
        raise Exception("Dataset not restricted, no need to unlock")
    if len(metadata["private_files"]["archive_links"]) == 0 and len(metadata["private_files"]["files"]) == 0:
        raise Exception("No restricted files to unlock")

    # Set token in archive link URLs
    if len(metadata["private_files"]["archive_links"]) > 0:
        repo.git.checkout("git-annex")
        changes = False
        for link in metadata["private_files"]["archive_links"]:
            for dir_name, dirs, files in os.walk("."):
                for file_name in files:
                    file_path = os.path.join(dir_name, file_name)
                    if ".git" in file_path:
                        continue
                    with open(file_path, "r") as f:
                        s = f.read()
                    if link in s and "access_token" not in s:
                        changes = True
                        s = s.replace(link, link + "?access_token=" + token)
                        with open(file_path, "w") as f:
                            f.write(s)
        if changes:
            repo.git.add(".")
            repo.git.commit("-m", "Unlock dataset")
        repo.git.checkout("master")

    # Set token in non-archive link URLs
    if len(metadata["private_files"]["files"]) > 0:
        datalad = api.Dataset(".")
        for file in metadata["private_files"]["files"]:
            annex("rmurl", file["name"], file["link"])
            annex("addurl", file["link"] + "?access_token=" + token, "--file", file["name"], "--relaxed")
            datalad.save()

    print("Done")


if __name__ == "__main__":
    try:
        unlock()
    except Exception as e:
        traceback.print_exc()
    finally:
        # Always switch branch back to master
        repository = Repo()
        if repository.active_branch.name != "master":
            repository.git.checkout("master", "-f")