"""
CodeSentinel — Agent 2: Dependency Intelligence Agent
Real CVE lookups via OSV.dev (Google's open vulnerability database — free, no key needed).
Generates SBOM entries, license risk analysis, and abandoned package detection.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
import structlog

from app.agents.base_agent import AgentContext, AgentResult, BaseAgent
from app.ai import model_router
from app.ai.prompts.agent_prompts import DEPENDENCY_AGENT_SYSTEM

log = structlog.get_logger("agents.dependency")

OSV_API = "https://api.osv.dev/v1/query"
PYPI_API = "https://pypi.org/pypi/{package}/json"
NPM_API = "https://registry.npmjs.org/{package}"

# License risk classification
HIGH_RISK_LICENSES = {"AGPL-3.0", "GPL-3.0", "GPL-2.0", "LGPL-3.0", "SSPL-1.0"}
MEDIUM_RISK_LICENSES = {"LGPL-2.1", "MPL-2.0", "EUPL-1.2", "CPL-1.0"}
PERMISSIVE_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "Unlicense"}


@dataclass
class PackageInfo:
    name: str
    version: str
    ecosystem: str
    license: Optional[str] = None
    latest_version: Optional[str] = None
    last_published: Optional[str] = None
    is_deprecated: bool = False
    cves: list[dict] = field(default_factory=list)


def _parse_requirements_txt(content: str, path: str) -> list[dict]:
    """Parse Python requirements.txt into package list."""
    packages = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle == pins
        match = re.match(r'^([a-zA-Z0-9_\-\.\[\]]+)==([0-9][^\s;#]*)', line)
        if match:
            packages.append({"name": match.group(1).split("[")[0], "version": match.group(2), "ecosystem": "PyPI", "file": path})
            continue
        # Handle >= or other constraints
        match = re.match(r'^([a-zA-Z0-9_\-\.]+)([><=!~^]{1,2})([0-9][^\s;#]*)', line)
        if match:
            packages.append({"name": match.group(1), "version": match.group(3), "ecosystem": "PyPI", "file": path, "constraint": match.group(2)})
    return packages


def _parse_package_json(content: str, path: str) -> list[dict]:
    """Parse package.json dependencies."""
    packages = []
    try:
        data = json.loads(content)
        for dep_type in ["dependencies", "devDependencies", "peerDependencies"]:
            for name, version_spec in (data.get(dep_type) or {}).items():
                clean_version = version_spec.lstrip("^~>=<")
                if re.match(r'^\d', clean_version):
                    packages.append({"name": name, "version": clean_version, "ecosystem": "npm", "file": path, "dev": dep_type == "devDependencies"})
    except (json.JSONDecodeError, AttributeError):
        pass
    return packages


def _parse_go_mod(content: str, path: str) -> list[dict]:
    """Parse go.mod dependencies."""
    packages = []
    for line in content.split("\n"):
        match = re.match(r'^\s+([^\s]+)\s+v([^\s]+)', line)
        if match:
            packages.append({"name": match.group(1), "version": match.group(2), "ecosystem": "Go", "file": path})
    return packages


def _parse_gemfile_lock(content: str, path: str) -> list[dict]:
    """Parse Gemfile.lock."""
    packages = []
    in_gems = False
    for line in content.split("\n"):
        if line.strip() == "GEM":
            in_gems = True
        elif in_gems and line.startswith("    ") and not line.startswith("      "):
            match = re.match(r'\s+([a-zA-Z0-9_\-]+)\s+\(([0-9][^)]*)\)', line)
            if match:
                packages.append({"name": match.group(1), "version": match.group(2), "ecosystem": "RubyGems", "file": path})
        elif in_gems and not line.startswith(" "):
            in_gems = False
    return packages


async def _query_osv(package_name: str, version: str, ecosystem: str) -> list[dict]:
    """Query OSV.dev for known CVEs — free, no authentication needed."""
    payload = {
        "version": version,
        "package": {"name": package_name, "ecosystem": ecosystem},
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(OSV_API, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("vulns", [])
    except Exception as exc:
        log.debug("OSV query failed", package=package_name, error=str(exc))
    return []


async def _get_pypi_metadata(package_name: str) -> Optional[dict]:
    """Fetch PyPI package metadata for license and deprecation info."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(PYPI_API.format(package=package_name))
            if resp.status_code == 200:
                data = resp.json()
                info = data.get("info", {})
                return {
                    "license": info.get("license"),
                    "latest_version": info.get("version"),
                    "summary": info.get("summary", ""),
                    "is_yanked": any(
                        r.get("yanked") for releases in data.get("releases", {}).values() for r in releases
                    ),
                }
    except Exception:
        pass
    return None


async def _get_npm_metadata(package_name: str) -> Optional[dict]:
    """Fetch npm package metadata."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(NPM_API.format(package=package_name))
            if resp.status_code == 200:
                data = resp.json()
                latest = data.get("dist-tags", {}).get("latest", "")
                license_info = data.get("license") or (data.get("versions", {}).get(latest, {}) or {}).get("license", "")
                return {
                    "license": license_info if isinstance(license_info, str) else str(license_info),
                    "latest_version": latest,
                    "deprecated": data.get("deprecated"),
                }
    except Exception:
        pass
    return None


def _severity_from_osv(vuln: dict) -> tuple[str, float]:
    """Extract severity from OSV vulnerability data."""
    # Try CVSS v3 severity
    for severity in vuln.get("severity", []):
        score_str = severity.get("score", "")
        if "CVSS:3" in score_str:
            try:
                # Parse CVSS score from vector
                for part in score_str.split("/"):
                    if part.startswith("CVSS:3"):
                        pass
                # Try to get base score from database_specific
                pass
            except Exception:
                pass

    # Fall back to database-specific severity
    db_specific = vuln.get("database_specific", {})
    sev_str = db_specific.get("severity", "").upper()
    mapping = {"CRITICAL": ("critical", 9.5), "HIGH": ("high", 7.8), "MODERATE": ("medium", 5.5), "LOW": ("low", 2.5)}
    if sev_str in mapping:
        return mapping[sev_str]

    # Default to high for known CVEs (better to over-report than under)
    return "high", 7.0


def _classify_license_risk(license_str: Optional[str]) -> str:
    if not license_str:
        return "unknown"
    license_upper = license_str.upper().replace("-", "")
    for lic in HIGH_RISK_LICENSES:
        if lic.replace("-", "") in license_upper:
            return "high"
    for lic in MEDIUM_RISK_LICENSES:
        if lic.replace("-", "") in license_upper:
            return "medium"
    for lic in PERMISSIVE_LICENSES:
        if lic.replace("-", "") in license_upper:
            return "safe"
    return "unknown"


class DependencyAgent(BaseAgent):
    name = "dependency"
    display_name = "Dependency Intelligence Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        all_findings: list[dict] = []
        sbom_entries: list[dict] = []

        # ── Parse all manifests ────────────────────────────────────
        all_packages: list[dict] = []
        for path, content in ctx.manifests.items():
            filename = path.split("/")[-1].lower()
            if filename in ("requirements.txt", "requirements-dev.txt", "requirements-prod.txt"):
                all_packages.extend(_parse_requirements_txt(content, path))
            elif filename == "package.json":
                all_packages.extend(_parse_package_json(content, path))
            elif filename == "go.mod":
                all_packages.extend(_parse_go_mod(content, path))
            elif filename == "gemfile.lock":
                all_packages.extend(_parse_gemfile_lock(content, path))

        # Also check file_contents for manifest files
        for path, content in ctx.file_contents.items():
            filename = path.split("/")[-1].lower()
            if filename in ("requirements.txt", "package.json", "go.mod") and content:
                if filename == "requirements.txt":
                    existing_files = {p["file"] for p in all_packages}
                    if path not in existing_files:
                        all_packages.extend(_parse_requirements_txt(content, path))
                elif filename == "package.json":
                    existing_files = {p["file"] for p in all_packages}
                    if path not in existing_files:
                        all_packages.extend(_parse_package_json(content, path))

        if not all_packages:
            return AgentResult(
                agent_name=self.name,
                success=True,
                findings=[],
                extra={"packages_scanned": 0, "sbom": []},
            )

        log.info("Scanning dependencies", count=len(all_packages), scan_id=ctx.scan_id)

        # ── Query OSV.dev for each package (with concurrency limit) ──
        import asyncio
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent OSV requests

        async def check_package(pkg: dict):
            async with semaphore:
                name = pkg["name"]
                version = pkg["version"]
                ecosystem = pkg["ecosystem"]

                vulns = await _query_osv(name, version, ecosystem)

                # Fetch metadata for license + deprecation
                metadata = None
                if ecosystem == "PyPI":
                    metadata = await _get_pypi_metadata(name)
                elif ecosystem == "npm":
                    metadata = await _get_npm_metadata(name)

                license_str = (metadata or {}).get("license")
                license_risk = _classify_license_risk(license_str)

                sbom_entries.append({
                    "name": name,
                    "version": version,
                    "ecosystem": ecosystem,
                    "license": license_str or "Unknown",
                    "license_risk": license_risk,
                    "risk_level": "critical" if vulns else ("medium" if license_risk == "high" else "safe"),
                    "cve_count": len(vulns),
                    "file": pkg.get("file", ""),
                    "latest_version": (metadata or {}).get("latest_version"),
                    "deprecated": (metadata or {}).get("deprecated") or (metadata or {}).get("is_yanked"),
                })

                # Create findings for each CVE
                for vuln in vulns:
                    severity, cvss = _severity_from_osv(vuln)
                    osv_id = vuln.get("id", "")
                    aliases = vuln.get("aliases", [])
                    cve_id = next((a for a in aliases if a.startswith("CVE-")), None)

                    # Get affected version range and fixed version
                    fixed_version = None
                    for affected in vuln.get("affected", []):
                        for ranges in affected.get("ranges", []):
                            for event in ranges.get("events", []):
                                if "fixed" in event:
                                    fixed_version = event["fixed"]
                                    break

                    title = vuln.get("summary", f"Known vulnerability in {name}@{version}")
                    description = vuln.get("details", title)

                    finding = {
                        "rule_id": f"DEP-{osv_id}",
                        "cve_id": cve_id,
                        "title": f"{name}@{version}: {title[:150]}",
                        "description": description[:2000],
                        "why_flagged": (
                            f"Package '{name}' at version '{version}' is listed in {pkg.get('file', 'manifest')} "
                            f"and is known to be affected by {osv_id} ({cve_id or 'no CVE assigned'}). "
                            f"OSV.dev confirmed this version range is vulnerable."
                        ),
                        "business_risk": (
                            f"Dependency '{name}' contains a known {severity}-severity vulnerability. "
                            f"If exploited, this could allow attackers to {_vuln_business_impact(title, severity)}. "
                            f"Upgrade to {fixed_version or 'the latest version'} to remediate."
                        ),
                        "recommendation": (
                            f"Upgrade {name} from {version} to {fixed_version or 'latest'}. "
                            f"For pip: pip install --upgrade {name}{'==' + fixed_version if fixed_version else ''}. "
                            f"For npm: npm install {name}{'@' + fixed_version if fixed_version else '@latest'}."
                        ),
                        "file_path": pkg.get("file", ""),
                        "severity": severity,
                        "cvss_score": cvss,
                        "confidence": "high",
                        "category": "vulnerable_dependency",
                        "agent_type": "dependency",
                        "dependency_name": name,
                        "dependency_version": version,
                        "dependency_fixed_version": fixed_version,
                        "dependency_ecosystem": ecosystem,
                        "fix_available": fixed_version is not None,
                        "fix_complexity": "trivial",
                        "references": [
                            f"https://osv.dev/vulnerability/{osv_id}",
                            f"https://nvd.nist.gov/vuln/detail/{cve_id}" if cve_id else "",
                        ],
                        "compliance_frameworks": [],
                    }
                    finding["references"] = [r for r in finding["references"] if r]
                    all_findings.append(finding)

                # License risk finding
                if license_risk == "high":
                    all_findings.append({
                        "rule_id": f"LICENSE-{name.upper().replace('-', '_')}-001",
                        "title": f"High-risk license: {name} uses {license_str}",
                        "description": f"Package '{name}' is licensed under {license_str}, which has copyleft requirements that may force disclosure of proprietary code.",
                        "why_flagged": f"GPL/AGPL/LGPL licenses require that any software linking to or distributing {name} must also be open-sourced under the same license. This conflicts with commercial/proprietary software.",
                        "business_risk": f"Using {name} ({license_str}) in proprietary software without a commercial license may expose your company to legal liability and forced open-sourcing of your codebase.",
                        "recommendation": f"Consult legal counsel. Replace '{name}' with a permissively-licensed alternative, or obtain a commercial license if available.",
                        "file_path": pkg.get("file", ""),
                        "severity": "high",
                        "cvss_score": 6.0,
                        "confidence": "high",
                        "category": "license_risk",
                        "agent_type": "dependency",
                        "dependency_name": name,
                        "dependency_version": version,
                        "fix_available": False,
                        "fix_complexity": "manual",
                        "compliance_frameworks": [],
                    })

        await asyncio.gather(*[check_package(pkg) for pkg in all_packages])

        log.info(
            "Dependency scan complete",
            scan_id=ctx.scan_id,
            packages=len(all_packages),
            findings=len(all_findings),
        )

        return AgentResult(
            agent_name=self.name,
            success=True,
            findings=all_findings,
            extra={"packages_scanned": len(all_packages), "sbom": sbom_entries},
        )


def _vuln_business_impact(title: str, severity: str) -> str:
    title_lower = title.lower()
    if any(k in title_lower for k in ["rce", "remote code", "code execution"]):
        return "execute arbitrary code on your server, leading to complete system compromise"
    elif "injection" in title_lower:
        return "inject malicious data into your application, potentially exposing or corrupting your database"
    elif any(k in title_lower for k in ["dos", "denial of service", "infinite loop", "memory"]):
        return "crash or degrade your service, causing downtime and availability incidents"
    elif any(k in title_lower for k in ["bypass", "authentication", "authorization"]):
        return "bypass authentication or authorization controls, accessing protected resources"
    elif any(k in title_lower for k in ["disclosure", "exposure", "information leak"]):
        return "access sensitive information including user data, credentials, or system internals"
    elif any(k in title_lower for k in ["xss", "script"]):
        return "inject malicious scripts into your application, affecting other users"
    else:
        return f"exploit this {severity}-severity vulnerability in ways that could impact your service and users"
