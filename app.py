
from io import BytesIO
from urllib.parse import urlparse

from flask import Flask, render_template, request, send_file

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from github_api import (
    get_repository,
    get_languages,
    get_repository_structure,
    analyze_documentation,
    analyze_code_metrics,
    analyze_readme,
    analyze_dependencies,
    analyze_repository_risk,
    analyze_security_hygiene,
    get_repository_activity,
    get_contributor_analysis,
    analyze_issues_and_pull_requests,
)

app = Flask(__name__)


def parse_github_repo_url(repo_url):
    """Return owner and repository name from a GitHub URL."""
    try:
        parsed = urlparse((repo_url or "").strip())

        if parsed.scheme not in ("http", "https"):
            return None, None

        if parsed.netloc.lower() not in ("github.com", "www.github.com"):
            return None, None

        parts = [
            part for part in parsed.path.strip("/").split("/") if part
        ]

        if len(parts) != 2:
            return None, None

        owner, repo = parts
        repo = repo.removesuffix(".git")

        if not owner or not repo:
            return None, None

        return owner, repo

    except (TypeError, ValueError):
        return None, None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    repo_url = request.form.get("repo_url", "").strip()
    owner, repo = parse_github_repo_url(repo_url)

    if not owner or not repo:
        return render_template(
            "index.html",
            error=(
                "Please enter a valid GitHub repository URL, "
                "for example https://github.com/owner/repository."
            ),
        ), 400

    try:
        data = get_repository(owner, repo)

        if not isinstance(data, dict):
            return render_template(
                "index.html",
                error="Repository not found or unavailable. Check the URL.",
            ), 404

        languages_raw = get_languages(owner, repo) or {}

        branch = data.get("default_branch") or "main"

        structure = get_repository_structure(
            owner, repo, branch
        ) or []

        documentation = analyze_documentation(structure) or {}

        code_metrics = analyze_code_metrics(structure) or {}

        readme_analysis = analyze_readme(owner, repo) or {}

        dependency_analysis = analyze_dependencies(
            owner, repo, structure
        ) or {}

        risk_analysis = analyze_repository_risk(
            documentation,
            code_metrics,
            readme_analysis,
            dependency_analysis,
        ) or {}

        security_analysis = analyze_security_hygiene(
            structure
        ) or {}

        activity_analysis = get_repository_activity(
            owner, repo
        ) or {}

        contributor_analysis = get_contributor_analysis(
            owner, repo
        ) or {}

        issues_pr_analysis = analyze_issues_and_pull_requests(
            owner, repo
        ) or {}

        # Calculate programming-language percentages.
        total = sum(
            value
            for value in languages_raw.values()
            if isinstance(value, (int, float)) and value > 0
        )

        language_percentages = {}

        if total:
            for language, bytes_count in languages_raw.items():
                if (
                    isinstance(bytes_count, (int, float))
                    and bytes_count >= 0
                ):
                    language_percentages[language] = round(
                        (bytes_count / total) * 100, 2
                    )

        # Calculate documentation health score.
        health_score = 0

        for key in (
            "README",
            "License",
            "Requirements",
            "Tests",
            "Configuration",
        ):
            if documentation.get(key):
                health_score += 20

        # Generate recommendations.
        recommendations = []

        recommendation_map = {
            "README": "Add a README file to explain the project.",
            "License": (
                "Add a LICENSE file to define project usage rights."
            ),
            "Requirements": (
                "Add a dependency file such as requirements.txt."
            ),
            "Tests": "Add tests to improve project reliability.",
            "Configuration": (
                "Add configuration files if the project requires them."
            ),
        }

        for key, message in recommendation_map.items():
            if not documentation.get(key):
                recommendations.append(message)

        if health_score == 100:
            recommendations.append(
                "Excellent! The repository has all major quality components."
            )

        return render_template(
            "results.html",
            data=data,
            languages=language_percentages,
            structure=structure,
            documentation=documentation,
            health_score=health_score,
            recommendations=recommendations,
            code_metrics=code_metrics,
            readme_analysis=readme_analysis,
            dependency_analysis=dependency_analysis,
            risk_analysis=risk_analysis,
            security_analysis=security_analysis,
            activity_analysis=activity_analysis,
            contributor_analysis=contributor_analysis,
            issues_pr_analysis=issues_pr_analysis,
        )

    except Exception:
        app.logger.exception("Repository analysis failed")

        return render_template(
            "index.html",
            error=(
                "An error occurred while analyzing the repository. "
                "Check the terminal for details and try again."
            ),
        ), 500


@app.route("/compare", methods=["GET", "POST"])
def compare():
    if request.method == "GET":
        return render_template("compare.html")

    repo_url_1 = request.form.get("repo_url_1", "").strip()
    repo_url_2 = request.form.get("repo_url_2", "").strip()

    if not repo_url_1 or not repo_url_2:
        return render_template(
            "compare.html",
            error="Please enter both GitHub repository URLs.",
            repo_url_1=repo_url_1,
            repo_url_2=repo_url_2,
        ), 400

    owner_1, repo_1 = parse_github_repo_url(repo_url_1)
    owner_2, repo_2 = parse_github_repo_url(repo_url_2)

    if not owner_1 or not repo_1 or not owner_2 or not repo_2:
        return render_template(
            "compare.html",
            error=(
                "Enter two valid URLs, such as "
                "https://github.com/owner/repository."
            ),
            repo_url_1=repo_url_1,
            repo_url_2=repo_url_2,
        ), 400

    try:
        repository_1 = get_repository(owner_1, repo_1)
        repository_2 = get_repository(owner_2, repo_2)

        if not isinstance(repository_1, dict):
            return render_template(
                "compare.html",
                error=f"Repository 1 not found: {owner_1}/{repo_1}",
                repo_url_1=repo_url_1,
                repo_url_2=repo_url_2,
            ), 404

        if not isinstance(repository_2, dict):
            return render_template(
                "compare.html",
                error=f"Repository 2 not found: {owner_2}/{repo_2}",
                repo_url_1=repo_url_1,
                repo_url_2=repo_url_2,
            ), 404

        # Basic comparison data.
        comparison = {
            "stars_1": repository_1.get("stargazers_count", 0),
            "stars_2": repository_2.get("stargazers_count", 0),
            "forks_1": repository_1.get("forks_count", 0),
            "forks_2": repository_2.get("forks_count", 0),
            "issues_1": repository_1.get("open_issues_count", 0),
            "issues_2": repository_2.get("open_issues_count", 0),
        }

        return render_template(
            "compare.html",
            repo_url_1=repo_url_1,
            repo_url_2=repo_url_2,
            repository_1=repository_1,
            repository_2=repository_2,
            comparison=comparison,
            comparison_ready=True,
        )

    except Exception:
        app.logger.exception("Repository comparison failed")

        return render_template(
            "compare.html",
            error=(
                "Could not compare repositories. "
                "Check the terminal for details and try again."
            ),
            repo_url_1=repo_url_1,
            repo_url_2=repo_url_2,
        ), 500


@app.route("/download-report", methods=["GET"])
def download_report():
    """Generate a PDF summary of repository metadata and languages."""
    repo_url = request.args.get("repo_url", "").strip()
    owner, repo = parse_github_repo_url(repo_url)

    if not owner or not repo:
        return (
            "Invalid GitHub repository URL. "
            "Use https://github.com/owner/repository.",
            400,
        )

    try:
        data = get_repository(owner, repo)

        if not isinstance(data, dict):
            return "Repository not found or unavailable.", 404

        languages = get_languages(owner, repo) or {}

        if not isinstance(languages, dict):
            languages = {}

        pdf_buffer = BytesIO()

        document = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            rightMargin=0.6 * inch,
            leftMargin=0.6 * inch,
            topMargin=0.6 * inch,
            bottomMargin=0.6 * inch,
        )

        styles = getSampleStyleSheet()

        styles.add(
            ParagraphStyle(
                name="RepoLensReportTitle",
                parent=styles["Title"],
                alignment=TA_CENTER,
                textColor=colors.HexColor("#3730A3"),
                spaceAfter=16,
            )
        )

        story = [
            Paragraph("RepoLens", styles["RepoLensReportTitle"]),
            Paragraph(
                "GitHub Repository Summary Report",
                styles["Heading2"],
            ),
            Spacer(1, 12),
            Paragraph(
                "Repository Information",
                styles["Heading2"],
            ),
        ]

        description = data.get("description") or "No description provided."

        owner_data = data.get("owner") or {}

        if not isinstance(owner_data, dict):
            owner_data = {}

        rows = [
            ["Property", "Value"],
            [
                "Repository",
                str(data.get("full_name") or f"{owner}/{repo}"),
            ],
            ["Description", str(description)],
            ["Owner", str(owner_data.get("login") or owner)],
            [
                "Default branch",
                str(data.get("default_branch") or "N/A"),
            ],
            [
                "Visibility",
                "Private" if data.get("private") else "Public",
            ],
            ["Stars", str(data.get("stargazers_count", 0))],
            ["Forks", str(data.get("forks_count", 0))],
            [
                "Open issues",
                str(data.get("open_issues_count", 0)),
            ],
            ["Watchers", str(data.get("watchers_count", 0))],
            [
                "Repository URL",
                str(data.get("html_url") or repo_url),
            ],
        ]

        info_table = Table(
            rows,
            colWidths=[1.55 * inch, 5.05 * inch],
            repeatRows=1,
        )

        info_table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#3730A3"),
                ),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#CBD5E1"),
                ),
                (
                    "BACKGROUND",
                    (0, 1),
                    (0, -1),
                    colors.HexColor("#EEF2FF"),
                ),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )

        story.extend([
            info_table,
            Spacer(1, 18),
            Paragraph(
                "Programming Languages",
                styles["Heading2"],
            ),
        ])

        valid_languages = {
            name: count
            for name, count in languages.items()
            if isinstance(count, (int, float)) and count >= 0
        }

        total_bytes = sum(valid_languages.values())

        if valid_languages:
            language_rows = [["Language", "Bytes", "Percentage"]]

            for language, byte_count in sorted(
                valid_languages.items(),
                key=lambda item: item[1],
                reverse=True,
            ):
                percentage = (
                    byte_count / total_bytes * 100
                    if total_bytes
                    else 0
                )

                language_rows.append([
                    str(language),
                    f"{byte_count:,}",
                    f"{percentage:.1f}%",
                ])

            language_table = Table(
                language_rows,
                colWidths=[
                    2.7 * inch,
                    1.9 * inch,
                    2.0 * inch,
                ],
                repeatRows=1,
            )

            language_table.setStyle(
                TableStyle([
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#0F766E"),
                    ),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#CBD5E1"),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ])
            )

            story.append(language_table)

        else:
            story.append(
                Paragraph(
                    "No language statistics were returned.",
                    styles["BodyText"],
                )
            )

        story.extend([
            Spacer(1, 20),
            Paragraph(
                "Generated by RepoLens. This PDF includes repository "
                "metadata and programming-language statistics; it does "
                "not include every dashboard analysis or chart.",
                styles["Italic"],
            ),
        ])

        document.build(story)
        pdf_buffer.seek(0)

        safe_owner = "".join(
            ch for ch in owner if ch.isalnum() or ch in "-_"
        )

        safe_repo = "".join(
            ch for ch in repo if ch.isalnum() or ch in "-_"
        )

        filename = f"{safe_owner}_{safe_repo}_RepoLens_Report.pdf"

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )

    except Exception:
        app.logger.exception("PDF report generation failed")

        return (
            "Could not generate the PDF report. "
            "Check the terminal for details.",
            500,
        )


if __name__ == "__main__":
    app.run(debug=True)
