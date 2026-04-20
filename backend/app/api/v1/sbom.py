"""
CodeSentinel — SBOM API
Software Bill of Materials in SPDX 2.3 JSON format.
Aggregates dependency data from agent 2 scan results.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User

router = APIRouter()


@router.get("/sbom")
async def get_sbom_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return SBOM entries aggregated from all dependency agent scan results.
    Deduplicated by package name + version + ecosystem.
    """
    if not current_user.primary_org_id:
        return {"entries": [], "total": 0}

    repo_ids_r = await db.execute(
        select(Repository.id).where(Repository.organization_id == current_user.primary_org_id)
    )
    repo_ids = [str(r[0]) for r in repo_ids_r.fetchall()]
    if not repo_ids:
        return {"entries": [], "total": 0}

    # Get all dependency findings — they contain package metadata
    result = await db.execute(
        select(Finding)
        .join(Repository, Finding.repository_id == Repository.id)
        .where(
            Repository.organization_id == current_user.primary_org_id,
            Finding.agent_type == "dependency",
            Finding.dependency_name.isnot(None),
        )
    )
    findings = result.scalars().all()

    # Deduplicate by name+version+ecosystem
    seen: set[str] = set()
    entries: list[dict] = []
    for f in findings:
        key = f"{f.dependency_name}@{f.dependency_version}@{f.dependency_ecosystem}"
        if key in seen:
            continue
        seen.add(key)
        entries.append({
            "name": f.dependency_name,
            "version": f.dependency_version,
            "ecosystem": f.dependency_ecosystem or "unknown",
            "license": "Unknown",
            "license_risk": "unknown",
            "cve_count": 1 if f.cve_id else 0,
            "risk_level": f.severity if f.cve_id else "safe",
            "file": f.file_path or "",
        })

    # Also pull SBOM entries from agent_results JSON in scans
    scans_r = await db.execute(
        select(Scan)
        .where(
            Scan.repository_id.in_(repo_ids),
            Scan.status.in_(["completed", "blocked"]),
            Scan.agent_results.isnot(None),
        )
        .order_by(Scan.created_at.desc())
        .limit(20)
    )
    scans = scans_r.scalars().all()

    for scan in scans:
        dep_results = (scan.agent_results or {}).get("dependency", {})
        for entry in dep_results.get("sbom", []):
            key = f"{entry.get('name')}@{entry.get('version')}@{entry.get('ecosystem')}"
            if key not in seen:
                seen.add(key)
                entries.append(entry)

    return {"entries": entries, "total": len(entries)}


@router.get("/sbom/summary")
async def sbom_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Summary stats for the SBOM page."""
    data = await get_sbom_data(current_user=current_user, db=db)
    entries = data["entries"]
    return {
        "entries": entries,
        "total": len(entries),
        "by_ecosystem": _count_by(entries, "ecosystem"),
        "by_risk": _count_by(entries, "risk_level"),
        "by_license_risk": _count_by(entries, "license_risk"),
    }


@router.get("/sbom/export")
async def export_sbom_spdx(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export SBOM in SPDX 2.3 JSON format.
    Returns a downloadable JSON file.
    """
    data = await get_sbom_data(current_user=current_user, db=db)
    entries = data["entries"]

    # Build SPDX 2.3 document
    spdx_doc = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"CodeSentinel-SBOM-{current_user.primary_org_id}",
        "documentNamespace": f"https://codesentinel.dev/sbom/{uuid.uuid4()}",
        "creationInfo": {
            "created": datetime.now(timezone.utc).isoformat(),
            "creators": ["Tool: CodeSentinel-1.0.0"],
        },
        "packages": [
            {
                "SPDXID": f"SPDXRef-Package-{i}",
                "name": e["name"],
                "versionInfo": e["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": e.get("license", "NOASSERTION"),
                "licenseDeclared": e.get("license", "NOASSERTION"),
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": f"purl:{e.get('ecosystem', 'generic').lower()}",
                        "referenceLocator": f"pkg:{e.get('ecosystem','generic').lower()}/{e['name']}@{e['version']}",
                    }
                ],
                "annotations": [
                    {
                        "annotationType": "REVIEW",
                        "annotator": "Tool: CodeSentinel",
                        "annotationDate": datetime.now(timezone.utc).isoformat(),
                        "comment": f"risk_level={e.get('risk_level','unknown')}; cve_count={e.get('cve_count',0)}",
                    }
                ] if e.get("cve_count", 0) > 0 else [],
            }
            for i, e in enumerate(entries)
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": f"SPDXRef-Package-{i}",
            }
            for i in range(len(entries))
        ],
    }

    json_content = json.dumps(spdx_doc, indent=2)
    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="sbom-{datetime.now(timezone.utc).strftime("%Y%m%d")}.spdx.json"'
        },
    )


def _count_by(entries: list[dict], field: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for e in entries:
        val = e.get(field, "unknown") or "unknown"
        result[val] = result.get(val, 0) + 1
    return result
