from __future__ import annotations

"""Render redacted report screenshots only from completed local test logs."""

from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/htunkhainglynn/Projects/aegis")
EVIDENCE = ROOT / "docs/evidence"
MONO = "/System/Library/Fonts/Menlo.ttc"


def read(name: str) -> list[str]:
    path = EVIDENCE / name
    if not path.exists():
        raise FileNotFoundError(f"Evidence log is missing: {path}")
    return [re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).replace("\r", "")
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]


def require(lines: list[str], fragments: list[str]) -> list[str]:
    selected: list[str] = []
    for fragment in fragments:
        match = next((line.strip() for line in lines if fragment in line), None)
        if match is None:
            raise RuntimeError(f"Verified evidence fragment not found: {fragment}")
        if match not in selected:
            selected.append(match)
    return selected


def wrap(text: str, width: int = 105) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if len(trial) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render(output: str, title: str, command: str, observed: list[str]) -> None:
    display: list[tuple[str, str]] = [("$ " + command, "#58a6ff")]
    for line in observed:
        for wrapped in wrap(line):
            display.append((wrapped, "#3fb950" if "PASS" in wrapped or "passed" in wrapped else "#c9d1d9"))
    display.append(("Observed locally: 21 August 2026 · secrets and generated credentials excluded", "#8b949e"))

    width = 1900
    line_height = 37
    height = 116 + line_height * len(display) + 30
    image = Image.new("RGB", (width, height), "#0d1117")
    draw = ImageDraw.Draw(image)
    body = ImageFont.truetype(MONO, 24)
    bold = ImageFont.truetype(MONO, 26)
    draw.rounded_rectangle((10, 10, width - 10, height - 10), radius=18, outline="#30363d", width=3)
    draw.ellipse((34, 29, 53, 48), fill="#ff5f56")
    draw.ellipse((66, 29, 85, 48), fill="#ffbd2e")
    draw.ellipse((98, 29, 117, 48), fill="#27c93f")
    draw.text((width // 2, 40), title, font=bold, fill="#f0f6fc", anchor="mm")
    y = 78
    for line, colour in display:
        draw.text((34, y), line, font=body, fill=colour)
        y += line_height
    image.save(EVIDENCE / output, dpi=(180, 180))


def main() -> None:
    cp = read("2026-08-21_control_plane_scenarios.txt")
    proxy = read("2026-08-21_proxy_scope_scenarios.txt")
    e2e = read("2026-08-21_e2e.txt")
    check = read("2026-08-21_make_check.txt")

    jobs = [
        ("tb1_login_request_evidence.png", "TB1 · Successful login request",
         "pytest login scenario; isolated Docker E2E",
         require(cp, ["test_login_and_refresh_tokens_include_current_email_and_role PASSED"]) +
         require(e2e, ["[PASS] Identity: valid admin login returned 200"])),
        ("tb1_rbac_rejection_evidence.png", "TB1 · Authentication and RBAC rejection",
         "pytest admin-only RBAC scenario; isolated Docker E2E",
         require(cp, ["test_user_management_is_admin_only PASSED"]) +
         require(e2e, ["[PASS] Authentication: invalid API key returned 401", "[PASS] Authorisation: revoked API key returned 403"])),
        ("tb2_api_key_creation_evidence.png", "TB2 · API-key creation and one-time secret",
         "pytest API-key lifecycle scenario; isolated Docker E2E",
         require(cp, ["test_create_api_key_returns_raw_key_once PASSED"]) +
         require(e2e, ["[PASS] API key: create returned 201", "[PASS] API key: a second key was created and revoked"])),
        ("tb2_invalid_policy_evidence.png", "TB2 · Invalid policy payload rejected",
         "pytest route-permission schema and duplicate-policy validation",
         require(cp, ["test_route_permission_validation_and_duplicate_active_scope PASSED", "4 passed, 3 warnings"])),
        ("tb3_exact_scope_allow_evidence.png", "TB3 · Exact route scope allowed",
         "go test -v proxy scope scenarios",
         require(proxy, ["TestHasScopeRequiresExactScope/specific_match (0.00s)", "TestHandlerEnforcesBackendRoutePermissionPolicy/matching_scope_allowed (0.00s)"])),
        ("tb3_insufficient_scope_evidence.png", "TB3 · Insufficient scope denied",
         "go test -v proxy scope scenarios",
         require(proxy, ["TestHasScopeRequiresExactScope/missing_write (0.00s)", "TestHandlerEnforcesBackendRoutePermissionPolicy/missing_scope_denied (0.00s)"])),
        ("tb4_rate_limit_sequence_evidence.png", "TB4 · Redis rate-limit sequence",
         "isolated Docker E2E",
         require(e2e, ["[PASS] Rate policy: global fixed-window rule", "[PASS] Rate enforcement: request statuses were 200, 200, 429"])),
        ("tb4_threat_ip_evidence.png", "TB4 · Threat and exact-IP enforcement",
         "isolated Docker E2E",
         require(e2e, ["[PASS] IP enforcement: exact direct-peer block returned 403", "[PASS] Threat enforcement: matching request returned 403", "[PASS] Automatic protection: repeated violations produced 403"])),
        ("tb5_policy_distribution_evidence.png", "TB5 · Authenticated policy distribution",
         "isolated Docker E2E",
         require(e2e, ["[PASS] JWT policy: HS256 configuration created and activated", "[PASS] Policy distribution: authenticated gRPC snapshot enabled a 200 upstream response"])),
        ("tb5_analytics_evidence.png", "TB5 · Security analytics populated",
         "isolated Docker E2E",
         require(e2e, ["[PASS] Analytics: forwarded, blocked, threat and rate-limit events were aggregated", "[PASS] Persistence: the automatic active IP block appears"])),
        ("tb6_integrated_health_evidence.png", "TB6 · Integrated service health",
         "isolated Docker E2E",
         require(e2e, ["[PASS] Health: Control Plane 200", "[PASS] Dashboard: login page returned 200"]) +
         require(check, ["47 passed, 4 warnings", "Reverse proxy core coverage: 83.4%", "13 passed in"])),
        ("tb6_end_to_end_evidence.png", "TB6 · End-to-end allow and deny verification",
         "./scripts/e2e.sh",
         require(e2e, ["[PASS] Policy distribution: authenticated gRPC snapshot enabled a 200 upstream response", "[PASS] Threat enforcement: matching request returned 403", "[PASS] Rate enforcement: request statuses were 200, 200, 429", "E2E passed:"])),
    ]

    for output, title, command, lines in jobs:
        render(output, title, command, lines)


if __name__ == "__main__":
    main()
