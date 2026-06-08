"""시뮬레이션 전용 도구 구현.

각 도구는 World State DB를 실제 외부 시스템 대신 조작한다.
모든 쓰기 작업은 감사 로그(audit_log)에도 기록된다.

도구 입력에 scenario_id를 포함시켜 self-contained하게 동작한다.
DB 세션은 내부적으로 AsyncSessionLocal()로 생성한다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.database import AsyncSessionLocal
from app.services import world_state_service as ws
from app.services.audit_service import write_log


# ── 내부 헬퍼 ────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _audit(action: str, outcome: str, resource_id: str | None, metadata: dict | None = None) -> None:
    """시뮬레이션 도구 호출을 감사 로그에 기록."""
    try:
        async with AsyncSessionLocal() as db:
            await write_log(
                db,
                action=action,
                outcome=outcome,
                actor_type="agent",
                resource_type="simulation",
                resource_id=resource_id,
                metadata=metadata,
            )
            await db.commit()
    except Exception:
        pass  # 감사 실패가 도구 실행을 막지 않음


# ── 요구사항 조회 ────────────────────────────────────────────────────

async def read_requirements(scenario_id: str, status: str | None = None) -> str:
    """World State의 requirements 섹션을 읽어 반환."""
    async with AsyncSessionLocal() as db:
        state = await ws.get_world_state(db, scenario_id)

    if state is None:
        return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."

    items = state.get("requirements", [])
    if status:
        items = [r for r in items if r.get("status") == status]

    if not items:
        return "등록된 요구사항이 없습니다."

    lines = [f"[요구사항 목록 — scenario: {scenario_id}]"]
    for r in items:
        lines.append(
            f"• [{r['id']}] ({r.get('priority','?').upper()}) {r['content']}"
            f"\n  출처: {r.get('from_customer','?')} | 상태: {r.get('status','?')}"
        )

    await _audit("sim.read_requirements", "success", scenario_id, {"status_filter": status})
    return "\n".join(lines)


# ── 티켓 조회 ────────────────────────────────────────────────────────

async def read_tickets(scenario_id: str, status: str | None = None, assignee_role: str | None = None) -> str:
    """World State의 tickets 섹션을 읽어 반환. status / assignee_role 필터 지원."""
    async with AsyncSessionLocal() as db:
        state = await ws.get_world_state(db, scenario_id)

    if state is None:
        return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."

    items = state.get("tickets", [])
    if status:
        items = [t for t in items if t.get("status") == status]
    if assignee_role:
        items = [t for t in items if t.get("assignee_role") == assignee_role]

    if not items:
        return "조건에 맞는 티켓이 없습니다."

    lines = [f"[티켓 목록 — scenario: {scenario_id}]"]
    for t in items:
        lines.append(
            f"• [{t['id']}] {t['title']}"
            f"\n  우선순위: {t.get('priority','?')} | 상태: {t.get('status','?')} | 담당: {t.get('assignee_role','?')}"
            f"\n  설명: {t.get('description','')}"
        )

    await _audit("sim.read_tickets", "success", scenario_id,
                 {"status_filter": status, "role_filter": assignee_role})
    return "\n".join(lines)


# ── 티켓 생성 ────────────────────────────────────────────────────────

async def create_ticket(
    scenario_id: str,
    title: str,
    assignee_role: str,
    description: str = "",
    priority: str = "medium",
) -> str:
    """새 티켓을 World State에 추가."""
    ticket_id = f"TICK-{uuid.uuid4().hex[:4].upper()}"
    new_ticket = {
        "id": ticket_id,
        "title": title,
        "status": "open",
        "priority": priority,
        "assignee_role": assignee_role,
        "description": description,
        "created_at": _now_iso(),
    }

    async with AsyncSessionLocal() as db:
        state = await ws.get_world_state(db, scenario_id)
        if state is None:
            return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."

        tickets = list(state.get("tickets", []))
        tickets.append(new_ticket)
        await ws.patch_world_state(db, scenario_id, "tickets", tickets)
        await ws.append_log(db, scenario_id, "INFO",
                            f"티켓 생성: [{ticket_id}] {title} (담당: {assignee_role})")
        await db.commit()

    await _audit("sim.create_ticket", "success", scenario_id,
                 {"ticket_id": ticket_id, "title": title, "assignee_role": assignee_role})
    return f"✅ 티켓 [{ticket_id}] '{title}'이 생성됐습니다. (담당: {assignee_role}, 우선순위: {priority})"


# ── 티켓 상태 변경 ───────────────────────────────────────────────────

async def update_ticket_status(scenario_id: str, ticket_id: str, status: str) -> str:
    """티켓 상태를 변경한다. status: open | in_progress | review | done | closed"""
    valid_statuses = {"open", "in_progress", "review", "done", "closed"}
    if status not in valid_statuses:
        return f"[오류] 유효하지 않은 상태입니다. 가능한 값: {sorted(valid_statuses)}"

    async with AsyncSessionLocal() as db:
        state = await ws.update_ticket_status(db, scenario_id, ticket_id, status)
        if state is None:
            return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."
        await ws.append_log(db, scenario_id, "INFO",
                            f"티켓 상태 변경: [{ticket_id}] → {status}")
        await db.commit()

    await _audit("sim.update_ticket_status", "success", scenario_id,
                 {"ticket_id": ticket_id, "new_status": status})
    return f"✅ 티켓 [{ticket_id}] 상태가 '{status}'로 변경됐습니다."


# ── 설계 문서 작성 ───────────────────────────────────────────────────

async def write_design_doc(scenario_id: str, title: str, content: str) -> str:
    """설계 문서를 codebase에 문서 파일로 기록."""
    doc_file = f"docs/{title.replace(' ', '_').lower()}.md"

    async with AsyncSessionLocal() as db:
        state = await ws.get_world_state(db, scenario_id)
        if state is None:
            return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."

        codebase = list(state.get("codebase", []))
        # 동일 파일이 있으면 버전 업
        existing = next((c for c in codebase if c["file"] == doc_file), None)
        if existing:
            existing["last_change"] = _now_iso()
            existing["note"] = f"문서 갱신: {content[:120]}"
        else:
            codebase.append({
                "file": doc_file,
                "version": "1.0.0",
                "last_change": _now_iso(),
                "note": f"설계 문서: {content[:120]}",
            })

        await ws.patch_world_state(db, scenario_id, "codebase", codebase)
        await ws.append_log(db, scenario_id, "INFO",
                            f"설계 문서 작성: {doc_file}")
        await db.commit()

    await _audit("sim.write_design_doc", "success", scenario_id,
                 {"file": doc_file, "title": title})
    return f"✅ 설계 문서 '{title}'이 {doc_file}에 저장됐습니다.\n\n[문서 내용 요약]\n{content[:500]}"


# ── 코드 커밋 ────────────────────────────────────────────────────────

async def commit_code(scenario_id: str, file: str, version: str, note: str = "") -> str:
    """코드 변경을 codebase에 커밋으로 기록."""
    async with AsyncSessionLocal() as db:
        state = await ws.get_world_state(db, scenario_id)
        if state is None:
            return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."

        codebase = list(state.get("codebase", []))
        existing = next((c for c in codebase if c["file"] == file), None)
        if existing:
            existing["version"] = version
            existing["last_change"] = _now_iso()
            existing["note"] = note or existing.get("note", "")
        else:
            codebase.append({
                "file": file,
                "version": version,
                "last_change": _now_iso(),
                "note": note,
            })

        await ws.patch_world_state(db, scenario_id, "codebase", codebase)
        await ws.append_log(db, scenario_id, "INFO",
                            f"코드 커밋: {file} → v{version}  {note}")
        await db.commit()

    await _audit("sim.commit_code", "success", scenario_id,
                 {"file": file, "version": version})
    return f"✅ [{file}] v{version} 커밋 완료. {note}"


# ── 가상 배포 ────────────────────────────────────────────────────────

async def deploy(scenario_id: str, version: str, note: str = "") -> str:
    """가상 배포를 실행하고 deployments에 기록한다."""
    deploy_id = f"DEPLOY-{uuid.uuid4().hex[:4].upper()}"
    new_deploy = {
        "id": deploy_id,
        "status": "live",
        "deployed_at": _now_iso(),
        "version": version,
        "note": note or f"v{version} 배포",
    }

    async with AsyncSessionLocal() as db:
        state = await ws.get_world_state(db, scenario_id)
        if state is None:
            return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."

        deployments = list(state.get("deployments", []))
        # 이전 live 배포를 superseded로 전환
        for d in deployments:
            if d.get("status") == "live":
                d["status"] = "superseded"
        deployments.append(new_deploy)

        await ws.patch_world_state(db, scenario_id, "deployments", deployments)
        await ws.append_log(db, scenario_id, "INFO",
                            f"배포 완료: [{deploy_id}] v{version} → live")
        await db.commit()

    await _audit("sim.deploy", "success", scenario_id,
                 {"deploy_id": deploy_id, "version": version})
    return (
        f"🚀 배포 성공!\n"
        f"  배포 ID: {deploy_id}\n"
        f"  버전: v{version}\n"
        f"  상태: live\n"
        f"  시각: {_now_iso()}\n"
        f"  노트: {note or '없음'}"
    )


# ── 로그 조회 ────────────────────────────────────────────────────────

async def read_logs(scenario_id: str, level: str | None = None, limit: int = 20) -> str:
    """World State의 logs 섹션을 조회. level 필터 지원."""
    async with AsyncSessionLocal() as db:
        state = await ws.get_world_state(db, scenario_id)

    if state is None:
        return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."

    logs = state.get("logs", [])
    if level:
        logs = [l for l in logs if l.get("level", "").upper() == level.upper()]

    logs = logs[-limit:]  # 최근 N개
    if not logs:
        return "로그가 없습니다."

    lines = [f"[시스템 로그 — scenario: {scenario_id}]"]
    for l in logs:
        lines.append(f"[{l.get('level','?')}] {l.get('timestamp','?')[:19]}  {l.get('message','')}")

    await _audit("sim.read_logs", "success", scenario_id, {"level_filter": level})
    return "\n".join(lines)


# ── 인시던트 생성 ────────────────────────────────────────────────────

async def create_incident(scenario_id: str, message: str, level: str = "ERROR") -> str:
    """심각한 이슈를 INCIDENT 레벨 로그로 기록하고 티켓도 자동 생성한다."""
    valid_levels = {"WARN", "ERROR", "CRITICAL"}
    level = level.upper()
    if level not in valid_levels:
        level = "ERROR"

    incident_id = f"INC-{uuid.uuid4().hex[:4].upper()}"
    ticket_title = f"[인시던트] {message[:60]}"

    async with AsyncSessionLocal() as db:
        state = await ws.get_world_state(db, scenario_id)
        if state is None:
            return f"[오류] 시나리오 '{scenario_id}'를 찾을 수 없습니다."

        # 로그 기록
        await ws.append_log(db, scenario_id, level,
                            f"[{incident_id}] {message}")

        # 인시던트 티켓 자동 생성
        tickets = list(state.get("tickets", []))
        tickets.append({
            "id": incident_id,
            "title": ticket_title,
            "status": "open",
            "priority": "critical" if level == "CRITICAL" else "high",
            "assignee_role": "operator",
            "description": message,
            "created_at": _now_iso(),
        })
        await ws.patch_world_state(db, scenario_id, "tickets", tickets)
        await db.commit()

    await _audit("sim.create_incident", "success", scenario_id,
                 {"incident_id": incident_id, "level": level, "message": message[:200]})
    return (
        f"⚠️ 인시던트 [{incident_id}] 기록 완료\n"
        f"  레벨: {level}\n"
        f"  내용: {message}\n"
        f"  티켓 자동 생성됨 (담당: operator)"
    )
