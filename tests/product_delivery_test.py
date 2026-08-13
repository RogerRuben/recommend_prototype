# -*- coding: utf-8 -*-
from __future__ import print_function

import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.model_runtime import IntegratedModelRuntime
from app.product_releases import ProductReleaseService
from app.store import Store
from tools.product_delivery import (
    DeliveryError,
    build_delivery,
    install_delivery,
    rollback_delivery,
    verify_delivery,
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS - " + message)


def _business_package(temp_root):
    runtime = IntegratedModelRuntime(ROOT / "models")
    store = Store(
        temp_root / "source" / "data" / "source.db",
        ROOT / "data" / "virtual_protocol_dataset.csv",
        runtime,
        temp_root / "source" / "backups",
    )
    service = ProductReleaseService(store, runtime)
    # Delivery contract tests intentionally build a model-matched package.
    # Normal business-data drafts are empty and model-independent by default.
    release = service.create(seed_schema=True)
    path = temp_root / "business.iprelease.json"
    path.write_bytes(service.export_package(release["release_id"]))
    return path


def _rewrite_business_code(source, target, code):
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["product_code"] = code
    raw["data"]["products"][0]["product_code"] = code
    core = {
        "format": raw["format"],
        "product_code": raw["product_code"],
        "product_name": raw["product_name"],
        "data": raw["data"],
    }
    canonical = json.dumps(
        core, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    raw["payload_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    target.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_target(root):
    (root / "models").mkdir(parents=True)
    (root / "data").mkdir(parents=True)
    old_price = b'{"old":"price"}\n'
    old_effect = b'{"old":"effect"}\n'
    (root / "models" / "price_bundle.json").write_bytes(old_price)
    (root / "models" / "effectiveness_bundle.json").write_bytes(old_effect)
    conn = sqlite3.connect(str(root / "data" / "protocol_demo.db"))
    try:
        conn.execute("""CREATE TABLE product_releases(
            release_id TEXT PRIMARY KEY, product_code TEXT NOT NULL,
            product_name TEXT NOT NULL, status TEXT NOT NULL,
            data_json TEXT NOT NULL, validation_json TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            activated_at TEXT
        )""")
        conn.execute(
            """INSERT INTO product_releases VALUES
            ('REL-OLD','OLD','Old','draft','{}',NULL,'2026-01-01','2026-01-01',NULL)"""
        )
        conn.commit()
    finally:
        conn.close()
    return old_price, old_effect


def _release_count(db):
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("SELECT COUNT(*) FROM product_releases").fetchone()[0]
    finally:
        conn.close()


def main():
    temp_root = Path(tempfile.mkdtemp(prefix="ipdemo_delivery_"))
    try:
        business = _business_package(temp_root)
        package = temp_root / "demo_delivery.zip"
        try:
            build_delivery(
                ROOT / "models" / "price_bundle.json",
                ROOT / "models" / "effectiveness_bundle.json",
                business,
                package,
            )
            raise AssertionError("演示模型未显式授权时应拒绝构建")
        except DeliveryError as exc:
            check("--allow-demo-models" in str(exc), "演示模型必须显式授权后才能打包")

        built = build_delivery(
            ROOT / "models" / "price_bundle.json",
            ROOT / "models" / "effectiveness_bundle.json",
            business,
            package,
            delivery_version="delivery-test",
            allow_demo_models=True,
        )
        check(package.is_file() and Path(built["sha256_file"]).is_file(), "生成统一 ZIP 和外部 SHA-256 文件")
        check(not built["manifest"]["formal"], "演示模型交付包被明确标记为非正式")
        verified = verify_delivery(package, expected_sha256=built["sha256"])
        check(
            verified["manifest"]["cross_contract"]["valid"],
            "价格、效能和成品字段通过统一契约校验",
        )

        mismatch = temp_root / "mismatch.iprelease.json"
        _rewrite_business_code(business, mismatch, "ANOTHER_PRODUCT")
        try:
            build_delivery(
                ROOT / "models" / "price_bundle.json",
                ROOT / "models" / "effectiveness_bundle.json",
                mismatch,
                temp_root / "mismatch.zip",
                allow_demo_models=True,
            )
            raise AssertionError("成品代码不一致应拒绝打包")
        except DeliveryError as exc:
            check("product_code" in str(exc), "跨模型 product_code 不一致时拒绝打包")

        tampered = temp_root / "tampered.zip"
        with zipfile.ZipFile(str(package), "r") as source, zipfile.ZipFile(
            str(tampered), "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for info in source.infolist():
                raw = source.read(info.filename)
                if info.filename == "price/price_bundle.json":
                    raw += b"\n "
                target.writestr(info, raw)
        try:
            verify_delivery(tampered)
            raise AssertionError("篡改模型文件应验包失败")
        except DeliveryError as exc:
            check("校验失败" in str(exc), "模型文件被篡改后 SHA-256 校验失败")

        traversal = temp_root / "traversal.zip"
        shutil.copy2(str(package), str(traversal))
        with zipfile.ZipFile(str(traversal), "a") as archive:
            archive.writestr("../escape.txt", b"blocked")
        try:
            verify_delivery(traversal)
            raise AssertionError("目录穿越条目应验包失败")
        except DeliveryError as exc:
            check("非法包内路径" in str(exc), "验包拒绝 ZIP 目录穿越路径")

        redirected = temp_root / "redirected.zip"
        with zipfile.ZipFile(str(package), "r") as source, zipfile.ZipFile(
            str(redirected), "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for info in source.infolist():
                raw = source.read(info.filename)
                if info.filename == "delivery_manifest.json":
                    manifest = json.loads(raw.decode("utf-8"))
                    manifest["price"]["target"] = "README.md"
                    raw = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
                target.writestr(info, raw)
        try:
            verify_delivery(redirected)
            raise AssertionError("交付包不能重定向安装目标")
        except DeliveryError as exc:
            check("安装目标" in str(exc), "验包拒绝清单重定向项目内任意文件")

        target_root = temp_root / "target"
        old_price, old_effect = _make_target(target_root)
        try:
            install_delivery(
                package,
                project_root=target_root,
                enforce_stopped=False,
            )
            raise AssertionError("演示包未显式授权时应拒绝安装")
        except DeliveryError as exc:
            check("--allow-demo-models" in str(exc), "安装演示交付包也必须显式授权")

        installed = install_delivery(
            package,
            project_root=target_root,
            allow_demo_models=True,
            enforce_stopped=False,
        )
        check(
            (target_root / "models" / "price_bundle.json").read_bytes()
            == (ROOT / "models" / "price_bundle.json").read_bytes(),
            "安装价格模型到服务约定目标",
        )
        check(
            (target_root / "models" / "effectiveness_bundle.json").read_bytes()
            == (ROOT / "models" / "effectiveness_bundle.json").read_bytes(),
            "安装效能模型到服务约定目标",
        )
        check(_release_count(target_root / "data" / "protocol_demo.db") == 2, "成品数据仅导入为待校验草稿")
        check(
            (Path(installed["backup_path"]) / "install_record.json").is_file(),
            "安装前保存可审计备份记录",
        )

        rolled_back = rollback_delivery(
            installed["backup_id"], project_root=target_root, enforce_stopped=False
        )
        check(
            (target_root / "models" / "price_bundle.json").read_bytes() == old_price
            and (target_root / "models" / "effectiveness_bundle.json").read_bytes() == old_effect,
            "回滚恢复安装前的两个模型",
        )
        check(_release_count(target_root / "data" / "protocol_demo.db") == 1, "回滚恢复安装前的 SQLite 数据库")
        check(Path(rolled_back["pre_rollback_backup"]).is_dir(), "回滚前再次保留当前状态快照")

        failure_root = temp_root / "failure_target"
        failure_price, failure_effect = _make_target(failure_root)
        try:
            install_delivery(
                package,
                project_root=failure_root,
                allow_demo_models=True,
                enforce_stopped=False,
                _test_fail_after="effectiveness",
            )
            raise AssertionError("测试注入安装故障应抛出异常")
        except DeliveryError:
            pass
        check(
            (failure_root / "models" / "price_bundle.json").read_bytes() == failure_price
            and (failure_root / "models" / "effectiveness_bundle.json").read_bytes() == failure_effect
            and _release_count(failure_root / "data" / "protocol_demo.db") == 1,
            "安装中途失败时自动恢复所有已修改目标",
        )

        print(json.dumps({"status": "PASS", "checks": 17}, ensure_ascii=False))
    finally:
        shutil.rmtree(str(temp_root), ignore_errors=True)


if __name__ == "__main__":
    main()
