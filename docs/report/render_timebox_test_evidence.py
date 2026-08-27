from __future__ import annotations

"""Render compact terminal-style screenshots from verified timebox test logs."""

from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/htunkhainglynn/Projects/aegis")
EVIDENCE = ROOT / "docs/evidence"
FONT = "/System/Library/Fonts/Menlo.ttc"


def read(name: str) -> list[str]:
    return EVIDENCE.joinpath(name).read_text(encoding="utf-8", errors="replace").splitlines()


def matches(lines: list[str], patterns: list[str], limit: int = 24) -> list[str]:
    selected: list[str] = []
    for line in lines:
        clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).replace("\r", "")
        clean = clean.expandtabs(4).replace("ℹ", "INFO")
        if any(re.search(pattern, clean) for pattern in patterns):
            if clean not in selected:
                selected.append(clean)
        if len(selected) >= limit:
            break
    return selected


def terminal_image(title: str, command: str, lines: list[str], output: str) -> None:
    width = 1900
    line_height = 34
    height = 150 + line_height * (len(lines) + 2)
    image = Image.new("RGB", (width, height), "#0d1117")
    draw = ImageDraw.Draw(image)
    body = ImageFont.truetype(FONT, 24)
    bold = ImageFont.truetype(FONT, 25)
    draw.rounded_rectangle((12, 12, width - 12, height - 12), radius=18, outline="#30363d", width=3)
    draw.ellipse((34, 31, 52, 49), fill="#ff5f56")
    draw.ellipse((64, 31, 82, 49), fill="#ffbd2e")
    draw.ellipse((94, 31, 112, 49), fill="#27c93f")
    draw.text((width // 2, 40), title, font=bold, fill="#f0f6fc", anchor="mm")
    y = 78
    draw.text((34, y), "$ " + command, font=body, fill="#58a6ff")
    y += line_height + 10
    for line in lines:
        colour = "#3fb950" if ("passed" in line.lower() or "pass" in line or "ok  " in line or "✔" in line) else "#c9d1d9"
        draw.text((34, y), line[:122], font=body, fill=colour)
        y += line_height
    image.save(EVIDENCE / output, dpi=(180, 180))


def main() -> None:
    terminal_image(
        "TB1 - Identity and RBAC test evidence",
        "pytest -q tests/test_auth_and_user_rbac.py",
        matches(read("tb1_identity_tests.txt"), [r"passed", r"warnings summary"], 5),
        "tb1_identity_tests.png",
    )
    terminal_image(
        "TB2 - API key and policy test evidence",
        "pytest -q tests/test_api_keys.py tests/test_*rules.py tests/test_*configs.py tests/test_ip_blocks.py",
        matches(read("tb2_policy_tests.txt"), [r"passed"], 5),
        "tb2_policy_tests.png",
    )
    terminal_image(
        "TB3 - Proxy authentication and authorisation test evidence",
        "go test -v ./internal/proxy -run 'TestHandler|TestPolicyJWTValidator|TestAPIKeyValidation'",
        matches(read("tb3_proxy_auth_tests.txt"), [r"^--- PASS: Test", r"^PASS$", r"^ok\s"], 15),
        "tb3_proxy_auth_tests.png",
    )
    terminal_image(
        "TB4 - Rate limit, threat and IP enforcement test evidence",
        "go test -v ./internal/proxy -run 'TestRedisRateLimiter|TestPolicyThreatDetector|TestPolicyIPBlocker'",
        matches(read("tb4_limits_threats_tests.txt"), [r"^--- PASS: Test", r"^PASS$", r"^ok\s"], 16),
        "tb4_limits_threats_tests.png",
    )
    terminal_image(
        "TB5 - Policy distribution, analytics and dashboard test evidence",
        "pytest grpc/analytics; go test controlplane; npm test",
        matches(
            read("tb5_distribution_dashboard_tests.txt"),
            [r"passed in", r"^--- PASS: Test", r"^PASS$", r"^ok\s", r"^✔", r"^ℹ pass", r"^ℹ fail"],
            22,
        ),
        "tb5_distribution_dashboard_tests.png",
    )
    terminal_image(
        "TB6 - Complete release quality-gate evidence",
        "make check",
        matches(
            read("tb6_full_quality_gate.txt"),
            [r"47 passed", r"^TOTAL", r"^ok\s+github.com", r"core coverage", r"^✔", r"^ℹ pass", r"^ℹ fail", r"13 passed"],
            24,
        ),
        "tb6_full_quality_gate.png",
    )


if __name__ == "__main__":
    main()
