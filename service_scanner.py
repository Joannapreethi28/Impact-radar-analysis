import os

def scan_project(folder_path):

    modules = []

    for root, dirs, files in os.walk(folder_path):

        for file in files:

            if file.endswith(".py"):
                modules.append(
                    file.replace(".py", "")
                )

    return modules
