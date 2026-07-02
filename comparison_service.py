import os
import zipfile
import hashlib
import shutil
from datetime import datetime


# Folders that should not be scanned
SKIP_DIRS = {
    "venv", ".venv", "env", ".env",
    "__pycache__", ".git", ".idea", ".vscode",
    "site-packages", "dist-packages",
    "node_modules", "build", "dist"
}


def safe_extract_zip(zip_file, extract_to):
    """
    Safely extracts a ZIP file into the given folder.
    Old extracted content is removed before extraction.
    """

    if os.path.exists(extract_to):
        shutil.rmtree(extract_to)

    os.makedirs(extract_to, exist_ok=True)

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        for member in zip_ref.namelist():
            target_path = os.path.abspath(os.path.join(extract_to, member))
            extract_root = os.path.abspath(extract_to)

            # Prevent unsafe ZIP path traversal
            if not target_path.startswith(extract_root):
                raise Exception("Unsafe ZIP file detected")

        zip_ref.extractall(extract_to)

    return extract_to


def file_hash(file_path):
    """
    Creates a hash for a file.
    If the hash is different, the file content has changed.
    """

    hasher = hashlib.md5()

    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                hasher.update(chunk)

        return hasher.hexdigest()

    except OSError:
        return None


def normalize_path(path):
    """
    Converts Windows/Linux paths into one common format.
    """

    return path.replace("\\", "/").lower()


def should_skip_path(path):
    """
    Checks whether a path contains unwanted folders.
    """

    parts = normalize_path(path).split("/")

    for part in parts:
        if part in SKIP_DIRS:
            return True

    return False


def remove_common_zip_root(paths):
    """
    Removes the top-level folder from ZIP paths only when all files share
    the same root folder.

    Example:
    student_enrollment_full/services/student_service.py
    becomes:
    services/student_service.py

    This prevents this false result:
    old ZIP  : student_enrollment_full/student_service.py
    new ZIP  : student_enrollment_without_db/student_service.py

    Without this fix, the system thinks student was deleted and added again.
    """

    if not paths:
        return {}

    split_paths = [path.split("/") for path in paths]

    # Remove root only if every file has at least two parts
    # and all first folder names are the same.
    if all(len(parts) > 1 for parts in split_paths):
        first_roots = {parts[0] for parts in split_paths}

        if len(first_roots) == 1:
            return {
                path: "/".join(path.split("/")[1:])
                for path in paths
            }

    return {path: path for path in paths}


def map_to_business_module(file_path):
    """
    Maps technical file names into business-level modules.

    Examples:
    student_service.py        -> student
    student_repository.py     -> student
    teacher_model.py          -> teacher
    enrollment_service.py     -> enrollment
    db.py / database.py       -> db
    """

    path = normalize_path(file_path)
    filename = os.path.basename(path)

    if "db" in filename or "database" in path:
        return "db"

    if "student" in path:
        return "student"

    if "teacher" in path:
        return "teacher"

    if "enrollment" in path or "enrolment" in path:
        return "enrollment"

    return os.path.splitext(filename)[0]


def collect_python_files(project_folder):
    """
    Collects all Python files from a project folder.

    Returns:
    {
        "services/student_service.py": {
            "hash": "...",
            "business_module": "student"
        }
    }
    """

    raw_files = {}

    for root, dirs, files in os.walk(project_folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for file in files:
            if not file.endswith(".py"):
                continue

            full_path = os.path.join(root, file)

            if should_skip_path(full_path):
                continue

            relative_path = os.path.relpath(full_path, project_folder)
            relative_path = normalize_path(relative_path)

            raw_files[relative_path] = full_path

    # Fix ZIP root folder mismatch
    normalized_map = remove_common_zip_root(list(raw_files.keys()))

    files_data = {}

    for original_relative_path, normalized_relative_path in normalized_map.items():
        full_path = raw_files[original_relative_path]

        files_data[normalized_relative_path] = {
            "hash": file_hash(full_path),
            "business_module": map_to_business_module(normalized_relative_path)
        }

    return files_data


def compare_project_folders(old_folder, modified_folder):
    """
    Compares old project folder and modified project folder.

    Detects:
    - changed files
    - deleted files
    - added files

    Business-level classification:
    - missing module: module existed in old version but completely absent in new version
    - added module: module did not exist in old version but appears in new version
    - changed module: module exists in both versions but one of its files changed/added/deleted
    """

    old_files = collect_python_files(old_folder)
    new_files = collect_python_files(modified_folder)

    old_paths = set(old_files.keys())
    new_paths = set(new_files.keys())

    deleted_files = sorted(old_paths - new_paths)
    added_files = sorted(new_paths - old_paths)

    changed_files = []
    for path in sorted(old_paths & new_paths):
        old_hash = old_files[path]["hash"]
        new_hash = new_files[path]["hash"]

        if old_hash != new_hash:
            changed_files.append(path)

    old_modules = {
        data["business_module"]
        for data in old_files.values()
    }

    new_modules = {
        data["business_module"]
        for data in new_files.values()
    }

    # Entire business module removed
    missing_modules = sorted(old_modules - new_modules)

    # Entire new business module introduced
    added_modules = sorted(new_modules - old_modules)

    common_modules = old_modules & new_modules

    changed_modules_set = set()

    # Same file exists in both versions but content changed
    for path in changed_files:
        changed_modules_set.add(new_files[path]["business_module"])

    # File deleted inside an existing module means module changed,
    # not necessarily the whole module is missing.
    for path in deleted_files:
        module = old_files[path]["business_module"]
        if module in common_modules:
            changed_modules_set.add(module)

    # File added inside an existing module means module changed,
    # not a completely new module.
    for path in added_files:
        module = new_files[path]["business_module"]
        if module in common_modules:
            changed_modules_set.add(module)

    changed_modules = sorted(changed_modules_set)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "changed_files": changed_files,
        "deleted_files": deleted_files,
        "added_files": added_files,

        "changed_modules": changed_modules,
        "missing_modules": missing_modules,
        "added_modules": added_modules
    }


def compare_project_zips(old_zip, modified_zip, work_dir="comparison_workspace"):
    """
    Compares old project ZIP and modified project ZIP.
    """

    old_extract_path = os.path.join(work_dir, "old_project")
    modified_extract_path = os.path.join(work_dir, "modified_project")

    safe_extract_zip(old_zip, old_extract_path)
    safe_extract_zip(modified_zip, modified_extract_path)

    return compare_project_folders(old_extract_path, modified_extract_path)


def generate_recommendations(changed_modules=None, missing_modules=None, added_modules=None):
    """
    Generates simple recommendation messages based on detected changes.
    """

    changed_modules = changed_modules or []
    missing_modules = missing_modules or []
    added_modules = added_modules or []

    recommendations = []

    for module in missing_modules:
        if module == "db":
            recommendations.append(
                "Restore the db module from the previous working version and retest student, teacher, and enrollment flows."
            )

        elif module == "student":
            recommendations.append(
                "Restore the student module and retest student management and enrollment creation."
            )

        elif module == "teacher":
            recommendations.append(
                "Restore the teacher module and retest teacher management and enrollment assignment."
            )

        elif module == "enrollment":
            recommendations.append(
                "Restore the enrollment module and retest enrollment creation, viewing, and deletion."
            )

        else:
            recommendations.append(
                f"Restore the missing {module} module and retest all modules depending on it."
            )

    for module in changed_modules:
        if module == "db":
            recommendations.append(
                "The db module has changed. Retest all database-related flows including student, teacher, and enrollment."
            )

        elif module == "student":
            recommendations.append(
                "The student module has changed. Retest student CRUD operations and enrollment creation."
            )

        elif module == "teacher":
            recommendations.append(
                "The teacher module has changed. Retest teacher CRUD operations and enrollment assignment."
            )

        elif module == "enrollment":
            recommendations.append(
                "The enrollment module has changed. Retest enrollment creation, viewing, and deletion."
            )

        else:
            recommendations.append(
                f"The {module} module has changed. Review dependent modules and perform regression testing."
            )

    for module in added_modules:
        recommendations.append(
            f"A new {module} module was added. Verify its dependencies and test integration with existing modules."
        )

    if not recommendations:
        recommendations.append(
            "No major file-level changes detected. Basic regression testing is sufficient."
        )

    return recommendations
def reverse_dependents(modules):
    """
    Converts dependency map into dependent map.

    Input:
    {
        "student": ["db"],
        "teacher": ["db"],
        "enrollment": ["student", "teacher"]
    }

    Output:
    {
        "db": {"student", "teacher"},
        "student": {"enrollment"},
        "teacher": {"enrollment"}
    }
    """

    dependents = {}

    for module, deps in modules.items():
        for dep in deps:
            if dep not in dependents:
                dependents[dep] = set()
            dependents[dep].add(module)

    return dependents


def compute_impact_for_module(modules, changed_module):
    """
    Finds direct and indirect impacted modules for one changed/missing module.
    """

    dependents = reverse_dependents(modules)

    direct = set(dependents.get(changed_module, set()))

    impacted = set()
    queue = list(direct)

    while queue:
        current = queue.pop(0)

        if current in impacted:
            continue

        impacted.add(current)

        for next_module in dependents.get(current, set()):
            if next_module not in impacted:
                queue.append(next_module)

    indirect = impacted - direct

    return {
        "changed_module": changed_module,
        "direct_impact": sorted(direct),
        "indirect_impact": sorted(indirect),
        "total_impacted": sorted(impacted)
    }


def compute_impact_for_detected_changes(modules, comparison_result):
    """
    Finds impacted modules for all automatically detected changed/missing modules.
    """

    changed_modules = comparison_result.get("changed_modules", [])
    missing_modules = comparison_result.get("missing_modules", [])

    affected_roots = sorted(set(changed_modules + missing_modules))

    all_direct = set()
    all_indirect = set()
    per_module_impact = {}

    for module in affected_roots:
        impact = compute_impact_for_module(modules, module)

        per_module_impact[module] = impact
        all_direct.update(impact["direct_impact"])
        all_indirect.update(impact["indirect_impact"])

    # Do not count the changed/missing module itself as impacted
    all_indirect = all_indirect - all_direct - set(affected_roots)

    return {
        "affected_roots": affected_roots,
        "direct_impact": sorted(all_direct),
        "indirect_impact": sorted(all_indirect),
        "total_impacted": sorted(all_direct | all_indirect),
        "per_module_impact": per_module_impact
    }


def assess_comparison_risk(total_impacted, total_modules):
    """
    Calculates risk level for version comparison.
    """

    ratio = len(total_impacted) / max(total_modules - 1, 1)

    if ratio >= 0.5:
        return "HIGH"
    elif ratio >= 0.25:
        return "MEDIUM"
    else:
        return "LOW"
