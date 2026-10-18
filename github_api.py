import requests
import base64
import json
import os

# ============================================================
# GITHUB API CONFIGURATION
# ============================================================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

API_BASE = "https://api.github.com"


def github_get(url, params=None):
    """Send a request to the GitHub API."""
    try:
        return requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=15
        )
    except requests.RequestException as error:
        print("GitHub API request failed:", error)
        return None


def get_repository(owner, repo):
    """Get basic repository information."""
    url = f"{API_BASE}/repos/{owner}/{repo}"
    response = github_get(url)

    if response and response.status_code == 200:
        return response.json()

    print("Repository API error:",
          response.status_code if response else "Request failed")
    return None


def get_languages(owner, repo):
    """Get repository programming languages."""
    url = f"{API_BASE}/repos/{owner}/{repo}/languages"
    response = github_get(url)

    if response and response.status_code == 200:
        return response.json()

    return {}


def get_repository_structure(owner, repo, branch):
    """Get the complete repository file tree."""
    url = (
        f"{API_BASE}/repos/{owner}/{repo}"
        f"/git/trees/{branch}"
    )

    response = github_get(url, {"recursive": "1"})

    if response and response.status_code == 200:
        return response.json()

    return {}


# ============================================================
# DOCUMENTATION ANALYSIS
# ============================================================

def analyze_documentation(structure):
    """Check for important project documentation files."""

    documentation = {
        "README": False,
        "License": False,
        "Requirements": False,
        "Tests": False,
        "Configuration": False
    }

    if not structure or "tree" not in structure:
        return documentation

    for item in structure["tree"]:
        path = item.get("path", "").lower()
        filename = path.split("/")[-1]

        if filename in ("readme", "readme.md", "readme.txt"):
            documentation["README"] = True

        if filename in (
            "license", "license.md", "license.txt",
            "licence", "licence.md"
        ):
            documentation["License"] = True

        if filename in (
            "requirements.txt", "pyproject.toml",
            "package.json", "pom.xml", "build.gradle"
        ):
            documentation["Requirements"] = True

        if (
            "test" in path
            or filename.startswith("test_")
            or filename.endswith("_test.py")
        ):
            documentation["Tests"] = True

        if (
            filename.endswith((".yml", ".yaml", ".json", ".ini"))
            or filename in (
                "dockerfile", ".env.example", "example.env",
                "makefile"
            )
        ):
            documentation["Configuration"] = True

    return documentation


# ============================================================
# CODE QUALITY METRICS
# ============================================================

def analyze_code_metrics(structure):
    """Count files and folders by common file type."""

    metrics = {
        "total_files": 0,
        "total_folders": 0,
        "python_files": 0,
        "html_files": 0,
        "css_files": 0,
        "javascript_files": 0,
        "documentation_files": 0,
        "other_files": 0
    }

    if not structure or "tree" not in structure:
        return metrics

    for item in structure["tree"]:
        path = item.get("path", "")
        item_type = item.get("type", "")

        if item_type == "tree":
            metrics["total_folders"] += 1
            continue

        if item_type != "blob":
            continue

        metrics["total_files"] += 1
        path_lower = path.lower()

        if path_lower.endswith(".py"):
            metrics["python_files"] += 1
        elif path_lower.endswith(".html"):
            metrics["html_files"] += 1
        elif path_lower.endswith(".css"):
            metrics["css_files"] += 1
        elif path_lower.endswith((".js", ".jsx", ".ts", ".tsx")):
            metrics["javascript_files"] += 1
        elif path_lower.endswith((".md", ".txt", ".rst")):
            metrics["documentation_files"] += 1
        else:
            metrics["other_files"] += 1

    return metrics


# ============================================================
# README ANALYSIS
# ============================================================

def analyze_readme(owner, repo):
    """Analyze README content and calculate a quality score."""

    result = {
        "available": False,
        "description": False,
        "installation": False,
        "usage": False,
        "features": False,
        "screenshots": False,
        "contributing": False,
        "license": False,
        "quality_score": 0
    }

    url = f"{API_BASE}/repos/{owner}/{repo}/readme"
    response = github_get(url)

    if not response or response.status_code != 200:
        return result

    data = response.json()
    result["available"] = True

    try:
        content = base64.b64decode(
            data.get("content", "")
        ).decode("utf-8", errors="ignore")
    except Exception as error:
        print("README decoding error:", error)
        return result

    content_lower = content.lower()

    result["description"] = len(content.strip()) > 100

    result["installation"] = any(
        word in content_lower
        for word in ("installation", "install", "setup")
    )

    result["usage"] = any(
        word in content_lower
        for word in (
            "usage", "how to use",
            "run the project", "getting started"
        )
    )

    result["features"] = (
        "features" in content_lower
        or "feature" in content_lower
    )

    result["screenshots"] = (
        "screenshot" in content_lower
        or "![" in content
        or "<img" in content_lower
    )

    result["contributing"] = any(
        word in content_lower
        for word in (
            "contributing", "contribution", "pull request"
        )
    )

    result["license"] = "license" in content_lower

    checks = [
        result["description"],
        result["installation"],
        result["usage"],
        result["features"],
        result["screenshots"],
        result["contributing"],
        result["license"]
    ]

    result["quality_score"] = round(
        sum(checks) / len(checks) * 100
    )

    return result


# ============================================================
# DEPENDENCY ANALYSIS
# ============================================================

def analyze_dependencies(owner, repo, structure):
    """Find and analyze a common dependency file."""

    result = {
        "available": False,
        "type": "None",
        "file": None,
        "dependencies": []
    }

    if not structure or "tree" not in structure:
        return result

    supported_files = {
        "requirements.txt": "Python",
        "package.json": "Node.js",
        "pyproject.toml": "Python",
        "pom.xml": "Java / Maven",
        "build.gradle": "Java / Gradle"
    }

    dependency_file = None

    for item in structure["tree"]:
        filename = item.get("path", "").lower()

        # This implementation checks root-level dependency files.
        if "/" not in filename and filename in supported_files:
            dependency_file = filename
            result["type"] = supported_files[filename]
            break

    if not dependency_file:
        return result

    result["available"] = True
    result["file"] = dependency_file

    url = (
        f"{API_BASE}/repos/{owner}/{repo}"
        f"/contents/{dependency_file}"
    )

    response = github_get(url)

    if not response or response.status_code != 200:
        return result

    try:
        data = response.json()
        content = base64.b64decode(
            data.get("content", "")
        ).decode("utf-8", errors="ignore")
    except Exception as error:
        print("Dependency decoding error:", error)
        return result

    if dependency_file == "requirements.txt":
        for line in content.splitlines():
            line = line.strip()

            if line and not line.startswith(("#", "-")):
                result["dependencies"].append(line)

    elif dependency_file == "package.json":
        try:
            package_data = json.loads(content)

            for name, version in package_data.get(
                "dependencies", {}
            ).items():
                result["dependencies"].append(
                    f"{name} {version}"
                )

            for name, version in package_data.get(
                "devDependencies", {}
            ).items():
                result["dependencies"].append(
                    f"{name} {version} (dev)"
                )

        except (ValueError, AttributeError) as error:
            print("package.json parsing error:", error)

    elif dependency_file == "pyproject.toml":
        # Simple text-based extraction of dependency entries.
        in_dependencies = False

        for line in content.splitlines():
            stripped = line.strip()

            if stripped.startswith("["):
                in_dependencies = (
                    stripped == "[project]"
                    or stripped == "[tool.poetry.dependencies]"
                )
                continue

            if in_dependencies and "=" in stripped:
                if not stripped.startswith("#"):
                    result["dependencies"].append(stripped)

    elif dependency_file == "pom.xml":
        for line in content.splitlines():
            if "<artifactId>" in line:
                name = (
                    line.replace("<artifactId>", "")
                    .replace("</artifactId>", "")
                    .strip()
                )
                if name:
                    result["dependencies"].append(name)

    elif dependency_file == "build.gradle":
        for line in content.splitlines():
            stripped = line.strip()

            if any(
                word in stripped
                for word in (
                    "implementation", "api ", "compile "
                )
            ):
                result["dependencies"].append(stripped)

    return result


# ============================================================
# REPOSITORY RISK ANALYSIS
# ============================================================

def analyze_repository_risk(
    documentation,
    code_metrics,
    readme_analysis,
    dependency_analysis
):
    """Calculate repository risk score and list risk factors."""

    risk_factors = []
    risk_score = 0

    if not documentation.get("README", False):
        risk_score += 20
        risk_factors.append("README file is missing.")

    if not documentation.get("License", False):
        risk_score += 15
        risk_factors.append("License file is missing.")

    if not documentation.get("Tests", False):
        risk_score += 25
        risk_factors.append("No tests were detected.")

    if not documentation.get("Requirements", False):
        risk_score += 15
        risk_factors.append("No dependency file was detected.")

    if readme_analysis.get("available", False):
        if readme_analysis.get("quality_score", 0) < 50:
            risk_score += 15
            risk_factors.append(
                "README quality is below 50%."
            )
    else:
        risk_score += 10
        risk_factors.append("README could not be analyzed.")

    if code_metrics.get("total_files", 0) > 500:
        risk_score += 10
        risk_factors.append(
            "Repository contains a large number of files."
        )

    if risk_score <= 20:
        risk_level = "LOW"
    elif risk_score <= 50:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    return {
        "score": risk_score,
        "level": risk_level,
        "factors": risk_factors
    }


# ============================================================
# SECURITY HYGIENE ANALYSIS
# ============================================================

def analyze_security_hygiene(structure):
    """Check common repository security hygiene indicators."""

    security = {
        "score": 100,
        "level": "GOOD",
        "issues": [],
        "warnings": [],
        "positive_checks": []
    }

    if not structure or "tree" not in structure:
        return security

    paths = [
        item.get("path", "").lower()
        for item in structure["tree"]
    ]

    filenames = [path.split("/")[-1] for path in paths]

    # Check .gitignore
    if ".gitignore" in filenames:
        security["positive_checks"].append(
            ".gitignore file is present."
        )
    else:
        security["score"] -= 20
        security["issues"].append(
            ".gitignore file is missing."
        )

    # Check whether a .env file is committed
    env_files = [
        path for path in paths
        if path.split("/")[-1] == ".env"
    ]

    if env_files:
        security["score"] -= 30
        security["issues"].append(
            "A .env file appears to be present in the repository."
        )
    else:
        security["positive_checks"].append(
            "No .env file detected."
        )

    # Check filenames that could contain secrets
    suspicious_names = {
        "secrets.json",
        "secret.json",
        "credentials.json",
        "credentials.txt",
        "api_keys.txt",
        "apikeys.txt",
        "private.key",
        "private.pem"
    }

    suspicious_files = [
        path for path in paths
        if path.split("/")[-1] in suspicious_names
    ]

    if suspicious_files:
        security["score"] -= 30
        security["issues"].append(
            "Potentially sensitive files were detected."
        )
    else:
        security["positive_checks"].append(
            "No obvious secret-like filenames detected."
        )

    # Check for an example environment file
    if ".env.example" in filenames or "example.env" in filenames:
        security["positive_checks"].append(
            ".env.example is available."
        )
    else:
        security["warnings"].append(
            "Consider adding an .env.example file for configuration guidance."
        )

    # Warn about configuration files that should be reviewed
    config_names = {
        ".env", "config.ini", "config.json", "settings.json"
    }

    if any(name in config_names for name in filenames):
        security["warnings"].append(
            "Review configuration files to ensure they contain no secrets."
        )

    security["score"] = max(0, security["score"])

    if security["score"] >= 80:
        security["level"] = "GOOD"
    elif security["score"] >= 50:
        security["level"] = "MEDIUM"
    else:
        security["level"] = "HIGH RISK"

    return security


# ============================================================
# CONTRIBUTOR ANALYSIS
# ============================================================

def get_contributor_analysis(owner, repo):
    """Return contributor usernames, profile links and contributions."""

    result = {
        "total_contributors": 0,
        "contributors": []
    }

    url = f"{API_BASE}/repos/{owner}/{repo}/contributors"
    response = github_get(url, {"per_page": 100})

    if not response or response.status_code != 200:
        return result

    try:
        contributors_data = response.json()
    except ValueError:
        return result

    if not isinstance(contributors_data, list):
        return result

    for contributor in contributors_data:
        result["contributors"].append({
            "username": contributor.get("login", "Unknown"),
            "contributions": contributor.get("contributions", 0),
            "avatar_url": contributor.get("avatar_url", ""),
            "profile_url": contributor.get("html_url", "")
        })

    result["contributors"].sort(
        key=lambda item: item["contributions"],
        reverse=True
    )

    result["total_contributors"] = len(result["contributors"])

    return result


# ============================================================
# REPOSITORY ACTIVITY ANALYSIS
# ============================================================

def get_repository_activity(owner, repo):
    """Analyze contributors, recent commits, issues and pull requests."""

    activity = {
        "contributors": 0,
        "commits": 0,
        "issues": 0,
        "pull_requests": 0,
        "last_commit": None,
        "activity_level": "LOW",
        "timeline": {}
    }

    # Contributors
    url = f"{API_BASE}/repos/{owner}/{repo}/contributors"
    response = github_get(url, {"per_page": 100})

    if response and response.status_code == 200:
        data = response.json()
        if isinstance(data, list):
            activity["contributors"] = len(data)

    # Commits and commit timeline
    url = f"{API_BASE}/repos/{owner}/{repo}/commits"
    response = github_get(url, {"per_page": 100})

    if response and response.status_code == 200:
        commits = response.json()

        if isinstance(commits, list):
            activity["commits"] = len(commits)

            if commits:
                activity["last_commit"] = (
                    commits[0]
                    .get("commit", {})
                    .get("author", {})
                    .get("date")
                )

            timeline = {}

            for commit in commits:
                date = (
                    commit.get("commit", {})
                    .get("author", {})
                    .get("date")
                )

                if date:
                    date_only = date[:10]
                    timeline[date_only] = (
                        timeline.get(date_only, 0) + 1
                    )

            activity["timeline"] = dict(sorted(timeline.items()))

    # Issues (GitHub's issues endpoint also returns PRs)
    url = f"{API_BASE}/repos/{owner}/{repo}/issues"
    response = github_get(
        url,
        {"state": "all", "per_page": 100}
    )

    if response and response.status_code == 200:
        items = response.json()

        if isinstance(items, list):
            activity["issues"] = sum(
                1 for item in items
                if "pull_request" not in item
            )

    # Pull requests
    url = f"{API_BASE}/repos/{owner}/{repo}/pulls"
    response = github_get(
        url,
        {"state": "all", "per_page": 100}
    )

    if response and response.status_code == 200:
        items = response.json()

        if isinstance(items, list):
            activity["pull_requests"] = len(items)

    score = (
        activity["contributors"]
        + activity["commits"]
        + activity["issues"]
        + activity["pull_requests"]
    )

    if score >= 100:
        activity["activity_level"] = "HIGH"
    elif score >= 20:
        activity["activity_level"] = "MEDIUM"
    else:
        activity["activity_level"] = "LOW"

    return activity


# ============================================================
# STEP 15 — ISSUE & PULL REQUEST ANALYSIS
# ============================================================

def get_all_pages(url, params=None):
    """Fetch all pages from a GitHub API endpoint."""

    all_items = []
    page = 1

    while True:
        page_params = dict(params or {})
        page_params.update({
            "per_page": 100,
            "page": page
        })

        response = github_get(url, page_params)

        if not response or response.status_code != 200:
            if response:
                print("GitHub API pagination error:", response.status_code)
            break

        page_data = response.json()

        if not isinstance(page_data, list) or not page_data:
            break

        all_items.extend(page_data)

        if len(page_data) < 100:
            break

        page += 1

    return all_items


def analyze_issues_and_pull_requests(owner, repo):
    """
    Analyze all issues and pull requests.

    Returns totals and status counts for:
    - Open and closed issues
    - Open, merged and unmerged closed pull requests
    """

    result = {
        "issues": {
            "total": 0,
            "open": 0,
            "closed": 0
        },
        "pull_requests": {
            "total": 0,
            "open": 0,
            "closed": 0,
            "merged": 0
        }
    }

    try:
        # ----------------------------------------------------
        # 1. ISSUES
        # ----------------------------------------------------
        issues_url = f"{API_BASE}/repos/{owner}/{repo}/issues"

        all_issues_and_prs = get_all_pages(
            issues_url,
            {"state": "all"}
        )

        # The Issues endpoint also includes pull requests.
        actual_issues = [
            issue for issue in all_issues_and_prs
            if "pull_request" not in issue
        ]

        result["issues"]["total"] = len(actual_issues)

        result["issues"]["open"] = sum(
            1 for issue in actual_issues
            if issue.get("state") == "open"
        )

        result["issues"]["closed"] = sum(
            1 for issue in actual_issues
            if issue.get("state") == "closed"
        )

        # ----------------------------------------------------
        # 2. PULL REQUESTS
        # ----------------------------------------------------
        pulls_url = f"{API_BASE}/repos/{owner}/{repo}/pulls"

        pull_requests = get_all_pages(
            pulls_url,
            {"state": "all"}
        )

        result["pull_requests"]["total"] = len(pull_requests)

        for pr in pull_requests:
            if pr.get("state") == "open":
                result["pull_requests"]["open"] += 1

            elif pr.get("state") == "closed":
                if pr.get("merged_at"):
                    result["pull_requests"]["merged"] += 1
                else:
                    result["pull_requests"]["closed"] += 1

        return result

    except Exception as error:
        print("Error analyzing issues and pull requests:", error)
        return result