"""Console app to launch Copilot CLI in a local git repository.

Accepts a root directory, prompts the user for a repo name, performs a
case-insensitive exact match against its immediate subfolders, and launches
Copilot CLI inside the matched folder. If no match is found, all discovered
repo names are printed and the user is prompted again.
"""

import argparse
import os
import subprocess
import sys

def list_repos(root):
    """Return the names of immediate subdirectories of root that are git repos."""
    return [
        entry.name
        for entry in os.scandir(root)
        if entry.is_dir() and os.path.isdir(os.path.join(entry.path, ".git"))
    ]


def get_active_branch(path):
    """Return the active git branch for the repo at path, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def find_repo(name, repos):
    """Return the matched repo name (case-insensitive exact) or None."""
    target = name.strip().casefold()
    for repo in repos:
        if repo.casefold() == target:
            return repo
    return None


def launch_copilot(path):
    """Launch Copilot CLI inline in the given folder."""
    print(f"Launching Copilot CLI in {path}...")
    try:
        command = "copilot" if os.name == "nt" else ["copilot"]
        subprocess.run(command, cwd=path, check=True, shell=os.name == "nt")
    except FileNotFoundError as exc:
        print("Error: 'copilot' command was not found in PATH.")
        raise SystemExit(1) from exc
    except subprocess.CalledProcessError as exc:
        print(f"Error: Copilot CLI exited with status {exc.returncode}.")
        raise SystemExit(exc.returncode) from exc


def parse_args():
    """Parse the command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Root folder of all git repos."
        )
    )
    parser.add_argument("root", help="Full path of the source folder.")
    return parser.parse_args()


def main():
    """Run the interactive repository selector and launch Copilot CLI."""
    root = parse_args().root
    if not os.path.isdir(root):
        print(f"Root folder '{root}' does not exist.")
        sys.exit(1)

    while True:
        repos = sorted(list_repos(root))
        print("Available repos:")
        for index, repo in enumerate(repos, start=1):
            branch = get_active_branch(os.path.join(root, repo))
            if branch:
                print(f"  {index}. {repo} ({branch})")
            else:
                print(f"  {index}. {repo}")

        name = input("Enter a repo number or name (blank or 'q' to quit): ").strip()
        if name == "" or name.casefold() == "q":
            print("Exiting.")
            return

        if name.isdigit():
            number = int(name)
            if 1 <= number <= len(repos):
                match = repos[number - 1]
            else:
                print(f"'{number}' is not a valid number.")
                continue
        else:
            match = find_repo(name, repos)
            if match is None:
                print(f"No repo named '{name}' found under {root}.")
                continue

        launch_copilot(os.path.join(root, match))
        return


if __name__ == "__main__":
    main()
