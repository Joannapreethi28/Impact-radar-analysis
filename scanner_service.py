import os
import re
import sys

SKIP_DIRS = {"venv", ".venv", "env", ".env", "virtualenv", ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules", "site-packages", "dist-packages", "build", "dist", ".tox", ".eggs", ".idea", ".vscode"}
EXTERNAL_ROOTS = {"streamlit", "pandas", "numpy", "matplotlib", "reportlab", "graphviz", "sklearn", "scipy", "seaborn", "flask", "django", "fastapi", "sqlalchemy", "requests", "urllib3", "six", "typing_extensions", "pydantic", "PIL", "cv2", "tensorflow", "torch", "keras", "plotly", "altair", "pydeck", "pytest", "setuptools", "pip", "wheel"}
COMMON_INTERNAL_ROOTS = {"controllers", "controller", "services", "service", "repositories", "repository", "models", "model", "database", "db", "utils", "config", "views", "view"}
FROM_RE = re.compile(r"^\s*from\s+([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)\s+import\s+([^#\n]+)", re.MULTILINE)
IMPORT_RE = re.compile(r"^\s*import\s+([^#\n]+)", re.MULTILINE)
try:
    STDLIB_ROOTS = set(sys.stdlib_module_names)
except AttributeError:
    STDLIB_ROOTS = {"os", "sys", "re", "json", "datetime", "math", "collections", "typing", "itertools", "functools", "pathlib", "io", "csv", "sqlite3", "random", "string", "subprocess", "time", "zipfile", "shutil", "hashlib"}


def _module_name(project_path, file_path):
    rel = os.path.relpath(file_path, project_path)
    name = rel[:-3].replace(os.sep, ".")
    if name.endswith(".__init__"):
        name = name[: -len(".__init__")]
    return name


def _clean_import_name(value):
    value = value.strip()
    if not value or value == "*":
        return ""
    return value.split(" as ", 1)[0].strip()


def _find_existing(import_path, existing_modules):
    parts = import_path.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in existing_modules:
            return candidate
    return None


def _is_probably_internal(import_path, local_roots):
    root = import_path.split(".", 1)[0]
    if root in STDLIB_ROOTS or root in EXTERNAL_ROOTS:
        return False
    if root in local_roots or root in COMMON_INTERNAL_ROOTS:
        return True
    return "." in import_path


def scan_project(project_path):
    file_contents, existing_modules, local_roots = {}, set(), set()
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for d in dirs:
            local_roots.add(d)
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            module = _module_name(project_path, path)
            existing_modules.add(module)
            local_roots.add(module.split(".", 1)[0])
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    file_contents[module] = f.read()
            except OSError:
                file_contents[module] = ""

    modules, missing_nodes = {}, set()
    for module in sorted(existing_modules):
        deps, seen = [], set()
        content = file_contents.get(module, "")
        def add(dep):
            if dep and dep != module and dep not in seen:
                seen.add(dep); deps.append(dep)
        for module_part, imported_part in FROM_RE.findall(content):
            module_part = _clean_import_name(module_part)
            imported_names = [_clean_import_name(x) for x in imported_part.split(",")]
            resolved = None
            for name in imported_names:
                candidate = f"{module_part}.{name}" if name else module_part
                resolved = _find_existing(candidate, existing_modules)
                if resolved:
                    break
            if not resolved:
                resolved = _find_existing(module_part, existing_modules)
            if resolved:
                add(resolved)
            elif _is_probably_internal(module_part, local_roots):
                missing = f"MISSING: {module_part}"
                missing_nodes.add(missing); add(missing)
        for import_line in IMPORT_RE.findall(content):
            for raw in import_line.split(","):
                import_path = _clean_import_name(raw)
                if not import_path:
                    continue
                resolved = _find_existing(import_path, existing_modules)
                if resolved:
                    add(resolved)
                elif _is_probably_internal(import_path, local_roots):
                    missing = f"MISSING: {import_path}"
                    missing_nodes.add(missing); add(missing)
        modules[module] = deps
    for missing in sorted(missing_nodes):
        modules.setdefault(missing, [])
    return modules
