# -*- coding: utf-8 -*-
"""Conditional-attribute advanced fold exists for admins and plain inactive hint for users."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_JS = ROOT / "app" / "static" / "admin.js"
APP_JS = ROOT / "app" / "static" / "app.js"


def main():
    admin = ADMIN_JS.read_text(encoding="utf-8")
    app = APP_JS.read_text(encoding="utf-8")

    assert "cond-template-advanced" in admin, "admin advanced fold missing"
    assert "JSON.stringify(template.rules" in admin, "admin advanced fold must show compiled rules"

    # User-facing inactive chip carries an advanced tooltip while keeping the plain label.
    assert "inactive_reason" in app
    assert "受控于" in app
    assert "无该属性" in app

    print(json.dumps({"status": "PASS", "message": "条件属性高级折叠与普通用户无该属性提示已具备"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
