# -*- coding: utf-8 -*-
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_admin_file_reader_never_surfaces_undefined():
    source = (ROOT / "app" / "static" / "admin.js").read_text(encoding="utf-8")
    assert 'r.onerror=function(){reject(new Error("浏览器无法读取该文件' in source
    assert 'r.onabort=function(){reject(new Error("文件读取已取消"))}' in source
    assert '服务器返回内容无法读取（HTTP ' in source
    assert "r.onerror=reject" not in source


if __name__ == "__main__":
    test_admin_file_reader_never_surfaces_undefined()
    print("PASS admin workbook errors are readable")
