# -*- coding: utf-8 -*-
"""Static guard: conditional-template admin buttons must not collide with generic CRUD handlers."""
from __future__ import print_function

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_JS = ROOT / "app" / "static" / "admin.js"


def main():
    source = ADMIN_JS.read_text(encoding="utf-8")

    # Conditional-template buttons must use their own classes only.
    assert 'class="cond-template-edit"' in source, "cond-template-edit class missing"
    assert 'class="cond-template-delete danger"' in source, "cond-template-delete class missing"
    assert 'edit-row cond-template-edit' not in source, "cond-template-edit still carries generic edit-row"
    assert 'purge-row cond-template-delete' not in source, "cond-template-delete still carries generic purge-row"

    # Generic CRUD handlers must be scoped to the main admin table, not the whole panel.
    assert 'q("mainAdminTable").querySelectorAll(".edit-row")' in source
    assert 'q("mainAdminTable").querySelectorAll(".toggle-row")' in source
    assert 'q("mainAdminTable").querySelectorAll(".archive-row")' in source
    assert 'q("mainAdminTable").querySelectorAll(".purge-row")' in source

    # Conditional-template handlers still exist and use the dedicated classes.
    assert 'document.querySelectorAll(".cond-template-edit")' in source
    assert 'document.querySelectorAll(".cond-template-delete")' in source

    # The main CRUD table carries the id used by the scoped handlers.
    assert 'id="mainAdminTable"' in source

    # Conditional-template editor now submits a V2 relationship payload.
    assert 'tpl.template="conditional_applicability_v2"' in source
    assert 'tpl.then={mode:"not_applicable"' in source
    assert 'otherwise_min' in source

    print(json.dumps({"status": "PASS", "message": "条件属性按钮与通用 CRUD 事件作用域已隔离"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
