import json
import os

FILE = "projects.json"


def load_projects():

    if not os.path.exists(FILE):
        return {}

    with open(FILE, "r") as f:
        return json.load(f)


def save_projects(projects):

    with open(FILE, "w") as f:
        json.dump(projects, f, indent=4)


def create_project(project_name):

    projects = load_projects()

    if project_name not in projects:
        projects[project_name] = {}

    save_projects(projects)


def add_module(project_name, module_name):

    projects = load_projects()

    if project_name not in projects:
        return False

    projects[project_name][module_name] = []

    save_projects(projects)

    return True


def add_dependency(project_name, module, dependency):

    projects = load_projects()

    if project_name not in projects:
        return False

    if module not in projects[project_name]:
        return False

    projects[project_name][module].append(dependency)

    save_projects(projects)

    return True
