import os
import re

def scan_project(project_path):

    modules = {}

    for root, dirs, files in os.walk(project_path):

        for file in files:

            if file.endswith(".py"):

                module_name = file.replace(".py", "")

                modules[module_name] = []

                file_path = os.path.join(root, file)

                with open(
                    file_path,
                    "r",
                    encoding="utf-8"
                ) as f:

                    content = f.read()

                imports = re.findall(
                    r'from\s+([a-zA-Z_][a-zA-Z0-9_]*)|import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                    content
                )

                for imp1, imp2 in imports:

                    dependency = imp1 if imp1 else imp2

                    if dependency and dependency != module_name:

                        modules[module_name].append(
                            dependency
                        )

    return modules
