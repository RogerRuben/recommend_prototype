# -*- coding: utf-8 -*-
"""Build, verify, install, and roll back one offline product delivery.

The delivery archive binds three independently maintained artifacts:

* the price-service model;
* the effectiveness-service model;
* an ``industrial-product-release-1.0`` business-data release.

Formal artifacts are validated by their native loaders while the archive is
built.  Installation deliberately performs static integrity and contract
checks only: installing an untrusted pickle must never execute it.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.product_releases import PACKAGE_FORMAT, SECTIONS
from app.historical_onboarding import HistoricalProductOnboarding
from app.store import _infer_model_value_mapping


DELIVERY_FORMAT = "industrial-product-delivery-1.0"
FORMAL_PRICE_BACKEND = "native_pickle"
FORMAL_EFFECT_BACKEND = "original_effectiveness_runtime"
FROZEN_EFFECT_BACKEND = "frozen_effectiveness_runtime"
FORMAL_EFFECT_BACKENDS = (FORMAL_EFFECT_BACKEND, FROZEN_EFFECT_BACKEND)
EXPECTED_PORTS = (18101, 18102, 17891)
MAX_ARCHIVE_FILES = 2000
MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024


class DeliveryError(RuntimeError):
    pass


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def _read_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise DeliveryError("%s不是有效的 UTF-8 JSON：%s" % (label, exc))


def _clean(value):
    return "" if value is None else str(value).strip()


def _boolish(value, default=False):
    if value in (None, ""):
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "no", "off", "否")


def _canonical_type(value):
    value = _clean(value).lower().replace("-", "_")
    aliases = {
        "float": "number",
        "double": "number",
        "numeric": "number",
        "continuous": "number",
        "int": "integer",
        "bool": "boolean",
        "category": "enum",
        "categorical": "enum",
        "choice": "enum",
        "string": "text",
        "str": "text",
    }
    return aliases.get(value, value or "number")


def _types_compatible(left, right):
    left, right = _canonical_type(left), _canonical_type(right)
    if left == right:
        return True
    if set((left, right)).issubset(set(("number", "integer"))):
        return True
    if set((left, right)).issubset(set(("integer", "ip_grade"))):
        return True
    if set((left, right)).issubset(set(("integer", "boolean"))):
        return True
    # Price regressors commonly receive booleans and IP grades after their
    # deterministic 0/1 or integer encoding, so a numeric model feature is
    # compatible with the richer product/editor type.
    if "number" in (left, right) and (
        "boolean" in (left, right) or "ip_grade" in (left, right)
    ):
        return True
    if set((left, right)).issubset(set(("text", "enum"))):
        return True
    return False


def _normalized_unit(value):
    return "".join(_clean(value).lower().split())


def _field_id(field):
    return _clean(field.get("field_name") or field.get("key") or field.get("parameter_id"))


def _field_type(field):
    return field.get("dtype") or field.get("type") or field.get("value_type") or "number"


def _index_fields(fields, source, errors):
    indexed = {}
    for field in fields or []:
        key = _field_id(field)
        if not key:
            errors.append("%s存在没有字段 ID 的定义" % source)
            continue
        if key in indexed:
            errors.append("%s存在重复字段 ID：%s" % (source, key))
            continue
        indexed[key] = field
    return indexed


def validate_business_release(raw):
    """Validate the portable business release without opening the application."""
    if not isinstance(raw, dict) or raw.get("format") != PACKAGE_FORMAT:
        raise DeliveryError("成品数据包格式必须是 %s" % PACKAGE_FORMAT)
    data = raw.get("data")
    if not isinstance(data, dict):
        raise DeliveryError("成品数据包缺少 data 对象")
    missing = [name for name in SECTIONS if not isinstance(data.get(name), list)]
    if missing:
        raise DeliveryError("成品数据包缺少模块：%s" % "、".join(missing))
    products = data.get("products") or []
    if len(products) != 1:
        raise DeliveryError("成品数据包必须且只能包含一条成品信息")
    code = _clean(products[0].get("product_code"))
    name = _clean(products[0].get("product_name"))
    if code != _clean(raw.get("product_code")) or name != _clean(raw.get("product_name")):
        raise DeliveryError("成品数据包头部与 products 模块不一致")
    core = {
        "format": PACKAGE_FORMAT,
        "product_code": code,
        "product_name": name,
        "data": data,
    }
    expected = _sha256_bytes(_canonical_json(core).encode("utf-8"))
    if _clean(raw.get("payload_sha256")) != expected:
        raise DeliveryError("成品数据包 payload_sha256 校验失败")
    return core


def cross_contract_report(price_schema, effect_schema, business_core):
    """Check product identity and the shared field contract."""
    errors, warnings = [], []
    business_code = _clean(business_core.get("product_code"))
    price_code = _clean(price_schema.get("product_code"))
    effect_code = _clean(effect_schema.get("product_code"))
    for source, code in (("价格模型", price_code), ("效能模型", effect_code)):
        if not code:
            errors.append("%s没有 product_code" % source)
        elif code != business_code:
            errors.append(
                "%s product_code=%s，与成品数据 %s 不一致"
                % (source, code, business_code)
            )

    price_fields = []
    for field in price_schema.get("fields") or []:
        if _clean(field.get("source") or "product_parameter") == "product_parameter":
            price_fields.append(field)
    effect_fields = effect_schema.get("fields") or []
    price_index = _index_fields(price_fields, "价格模型", errors)
    effect_index = _index_fields(effect_fields, "效能模型", errors)

    business_fields = business_core["data"].get("parameters") or []
    business_index = _index_fields(business_fields, "成品指标", errors)

    for key in sorted(set(price_index).intersection(effect_index)):
        left, right = price_index[key], effect_index[key]
        if not _types_compatible(_field_type(left), _field_type(right)):
            errors.append(
                "共享字段 %s 类型不一致：价格=%s，效能=%s"
                % (key, _field_type(left), _field_type(right))
            )
        left_unit, right_unit = _normalized_unit(left.get("unit")), _normalized_unit(right.get("unit"))
        if left_unit and right_unit and left_unit != right_unit:
            errors.append(
                "共享字段 %s 单位不一致：价格=%s，效能=%s"
                % (key, left.get("unit"), right.get("unit"))
            )

    required_model_fields = set(price_index).union(effect_index)
    for key in sorted(required_model_fields):
        if key not in business_index:
            errors.append("成品指标缺少模型字段：%s" % key)
            continue
        business = business_index[key]
        if not _boolish(business.get("enabled"), True):
            errors.append("模型字段在成品指标中被停用：%s" % key)
        if not _boolish(business.get("model_bound"), True):
            errors.append("模型字段未标记 model_bound：%s" % key)
        model_fields = [item for item in (price_index.get(key), effect_index.get(key)) if item]
        for model_field in model_fields:
            if not _types_compatible(business.get("value_type"), _field_type(model_field)):
                errors.append(
                    "字段 %s 的业务类型 %s 与模型类型 %s 不兼容"
                    % (key, business.get("value_type"), _field_type(model_field))
                )
            business_unit = _normalized_unit(business.get("unit"))
            model_unit = _normalized_unit(model_field.get("unit"))
            if business_unit and model_unit and business_unit != model_unit:
                errors.append(
                    "字段 %s 的业务单位 %s 与模型单位 %s 不一致"
                    % (key, business.get("unit"), model_field.get("unit"))
                )

    for key, field in sorted(business_index.items()):
        if _boolish(field.get("model_bound"), True) and key not in required_model_fields:
            warnings.append("业务字段 %s 标记为 model_bound，但两个模型均未声明" % key)

    counts = dict(
        (name, len(items))
        for name, items in business_core["data"].items()
        if isinstance(items, list)
    )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "product_code": business_code,
        "price_field_count": len(price_index),
        "effectiveness_field_count": len(effect_index),
        "shared_field_count": len(set(price_index).intersection(effect_index)),
        "model_parameter_count": len(required_model_fields),
        "business_counts": counts,
    }


def _load_price_for_build(path):
    from services.price_service.app import PriceService

    path = Path(path).resolve()
    if not path.is_file():
        raise DeliveryError("价格模型不存在：%s" % path)
    if path.suffix.lower() in (".pkl", ".pickle"):
        try:
            service = PriceService(model_path=path)
        except Exception as exc:
            raise DeliveryError("价格原生 bundle 加载校验失败：%s" % exc)
        backend = FORMAL_PRICE_BACKEND
        target = "services/price_service/model/price_native_bundle.pkl"
        payload = "price/price_native_bundle.pkl"
        extra = []
        sidecar = Path(str(path) + ".manifest.json")
        if sidecar.is_file():
            extra.append((sidecar, "price/price_native_bundle.pkl.manifest.json"))
    elif path.suffix.lower() == ".json":
        try:
            service = PriceService(fallback_json=path)
        except Exception as exc:
            raise DeliveryError("价格 JSON 模型加载校验失败：%s" % exc)
        backend = "portable_json"
        target = "models/price_bundle.json"
        payload = "price/price_bundle.json"
        extra = []
    else:
        raise DeliveryError("价格模型只支持 .pkl/.pickle 或 .json")
    return {
        "backend": backend,
        "formal": backend == FORMAL_PRICE_BACKEND,
        "schema": service.schema(),
        "source": path,
        "payload": payload,
        "target": target,
        "extra": extra,
    }


def _resolve_effect_manifest(path):
    path = Path(path).resolve()
    if path.is_dir():
        candidate = path / "effectiveness_runtime_manifest.json"
        if candidate.is_file():
            return candidate
        matches = list(path.glob("*runtime_manifest.json"))
        if len(matches) == 1:
            return matches[0]
        raise DeliveryError("效能运行包目录缺少 effectiveness_runtime_manifest.json")
    return path


def _load_effect_for_build(path):
    from services.effectiveness_service.app import SnapshotBackend, backend_from_package

    path = _resolve_effect_manifest(path)
    if not path.is_file():
        raise DeliveryError("效能模型不存在：%s" % path)
    if path.suffix.lower() == ".json":
        raw = _read_json(path, "效能模型")
        if raw.get("format_version") in (
            "effectiveness-original-runtime-package-1.0",
            "effectiveness-frozen-runtime-package-1.0",
        ):
            try:
                backend_object = backend_from_package(path)
            except Exception as exc:
                raise DeliveryError("效能正式运行包加载校验失败：%s" % exc)
            backend = backend_object.name
            target = "services/effectiveness_service/model/current"
            payload_root = "effectiveness/runtime"
            source_root = path.parent
            files = [(path, payload_root + "/effectiveness_runtime_manifest.json")]
            seen = {path.resolve()}
            for item in raw.get("files") or []:
                relative = _safe_relative_name(item.get("path"))
                source = (source_root / Path(*PurePosixPath(relative).parts)).resolve()
                if source_root not in source.parents:
                    raise DeliveryError("效能运行包文件越出根目录：%s" % relative)
                if source.resolve() not in seen:
                    files.append((source, payload_root + "/" + relative))
                    seen.add(source.resolve())
        else:
            try:
                backend_object = SnapshotBackend(path)
            except Exception as exc:
                raise DeliveryError("效能 JSON 快照加载校验失败：%s" % exc)
            backend = "snapshot_json"
            target = "models/effectiveness_bundle.json"
            payload_root = "effectiveness"
            files = [(path, "effectiveness/effectiveness_bundle.json")]
            raw = {}
    else:
        raise DeliveryError("效能模型必须是运行包 manifest 或 JSON 快照")
    return {
        "backend": backend,
        "formal": backend in FORMAL_EFFECT_BACKENDS,
        "schema": backend_object.schema(),
        "source": path,
        "payload_root": payload_root,
        "target": target,
        "files": files,
        "runtime_manifest": raw,
    }


def _safe_relative_name(name):
    name = _clean(name).replace("\\", "/")
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or ":" in path.parts[0]
    ):
        raise DeliveryError("非法包内路径：%s" % name)
    return path.as_posix()


def _copy_payload(source, stage, archive_name):
    archive_name = _safe_relative_name(archive_name)
    source = Path(source)
    if not source.is_file():
        raise DeliveryError("交付源文件不存在：%s" % source)
    target = stage / Path(*PurePosixPath(archive_name).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(target))
    return target


def _payload_entries(stage):
    entries = []
    for path in sorted(stage.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file() and path.name != "delivery_manifest.json":
            relative = path.relative_to(stage).as_posix()
            entries.append({
                "path": relative,
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            })
    return entries


def build_delivery(
    price_model,
    effectiveness_package,
    business_release,
    output,
    delivery_version=None,
    allow_demo_models=False,
    history_workbook=None,
    product_code=None,
    product_name=None,
    missing_tokens="-1,\\,/",
):
    """Create one validated ZIP and a companion SHA-256 text file."""
    price = _load_price_for_build(price_model)
    effect = _load_effect_for_build(effectiveness_package)
    business_path = None
    business_source = "prepared_release"
    if business_release:
        business_path = Path(business_release).resolve()
        business_raw = _read_json(business_path, "成品数据包")
    else:
        if not history_workbook:
            raise DeliveryError("必须提供 --business-release 或 --history-workbook")
        price_code = _clean(price["schema"].get("product_code"))
        effect_code = _clean(effect["schema"].get("product_code"))
        inferred_code = _clean(product_code) or price_code or effect_code
        inferred_name = (
            _clean(product_name)
            or _clean(effect["schema"].get("product_name"))
            or _clean(price["schema"].get("product_name"))
            or inferred_code
        )
        history_path = Path(history_workbook).resolve()
        if not history_path.is_file():
            raise DeliveryError("历史成品表不存在：%s" % history_path)
        try:
            report = HistoricalProductOnboarding().analyze(
                history_path.name,
                history_path.read_bytes(),
                inferred_code,
                inferred_name,
                missing_tokens=missing_tokens,
            )
        except Exception as exc:
            raise DeliveryError("历史成品表自动建包失败：%s" % exc)
        model_fields = {}
        for field in list(effect["schema"].get("fields") or []) + list(price["schema"].get("fields") or []):
            key = _field_id(field)
            if key and key not in model_fields:
                normalized = dict(field)
                normalized.setdefault("key", key)
                model_fields[key] = normalized
        for parameter in report["data"].get("parameters") or []:
            spec = model_fields.get(parameter.get("parameter_id"))
            parameter["model_bound"] = 1 if spec is not None else 0
            if spec is not None and not parameter.get("model_value_mapping_json"):
                mapping = _infer_model_value_mapping(parameter, spec)
                if mapping:
                    parameter["model_value_mapping_json"] = json.dumps(mapping, ensure_ascii=False)
        core = {
            "format": PACKAGE_FORMAT,
            "product_code": report["product_code"],
            "product_name": report["product_name"],
            "data": report["data"],
        }
        business_raw = dict(core)
        business_raw.update({
            "exported_at": _now(),
            "source_release_id": "AUTO-HISTORY",
            "source_status": "generated_from_history_workbook",
            "payload_sha256": _sha256_bytes(_canonical_json(core).encode("utf-8")),
            "onboarding_report": dict((key, value) for key, value in report.items() if key != "data"),
        })
        business_source = "history_workbook_auto_onboarding"
    business_core = validate_business_release(business_raw)
    formal = price["formal"] and effect["formal"]
    if not formal and not allow_demo_models:
        raise DeliveryError(
            "检测到演示模型后端（价格=%s，效能=%s）。如确需演示包，请显式添加 --allow-demo-models"
            % (price["backend"], effect["backend"])
        )
    if price["formal"] != effect["formal"] and not allow_demo_models:
        raise DeliveryError("不允许混合正式模型和演示模型")

    contract = cross_contract_report(price["schema"], effect["schema"], business_core)
    if not contract["valid"]:
        raise DeliveryError("跨模型契约校验失败：\n- " + "\n- ".join(contract["errors"]))

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    delivery_id = "DLV-%s-%s" % (_stamp(), uuid.uuid4().hex[:8].upper())
    with tempfile.TemporaryDirectory(prefix="product_delivery_build_") as temp:
        stage = Path(temp)
        business_payload = "business/product_release.iprelease.json"
        if business_path is not None:
            _copy_payload(business_path, stage, business_payload)
        else:
            target = stage / Path(*PurePosixPath(business_payload).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(business_raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _copy_payload(price["source"], stage, price["payload"])
        for source, archive_name in price["extra"]:
            _copy_payload(source, stage, archive_name)
        for source, archive_name in effect["files"]:
            _copy_payload(source, stage, archive_name)

        manifest = {
            "format_version": DELIVERY_FORMAT,
            "delivery_id": delivery_id,
            "delivery_version": _clean(delivery_version) or _stamp(),
            "created_at": _now(),
            "formal": formal,
            "product_code": business_core["product_code"],
            "product_name": business_core["product_name"],
            "business": {
                "format": PACKAGE_FORMAT,
                "payload": business_payload,
                "target": "data/protocol_demo.db",
                "activation_policy": "import_as_draft",
                "source": business_source,
                "counts": contract["business_counts"],
            },
            "price": {
                "backend": price["backend"],
                "formal": price["formal"],
                "model_version": price["schema"].get("model_version"),
                "payload": price["payload"],
                "target": price["target"],
                "schema": price["schema"],
            },
            "effectiveness": {
                "backend": effect["backend"],
                "formal": effect["formal"],
                "model_version": effect["schema"].get("model_version"),
                "payload_root": effect["payload_root"],
                "target": effect["target"],
                "schema": effect["schema"],
                "state_mode": effect["runtime_manifest"].get("state_mode"),
                "learning_fingerprint": effect["runtime_manifest"].get("learning_fingerprint"),
                "workbook_fingerprint": effect["runtime_manifest"].get("workbook_fingerprint"),
            },
            "cross_contract": contract,
            "files": _payload_entries(stage),
        }
        manifest["contract_sha256"] = _sha256_bytes(
            _canonical_json({
                "business": business_core,
                "price_schema": price["schema"],
                "effectiveness_schema": effect["schema"],
                "report": contract,
            }).encode("utf-8")
        )
        manifest_path = stage / "delivery_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with zipfile.ZipFile(
            str(output), "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as archive:
            for path in sorted(stage.rglob("*"), key=lambda item: item.as_posix()):
                if path.is_file():
                    archive.write(str(path), path.relative_to(stage).as_posix())

    archive_sha = _sha256_file(output)
    sha_path = Path(str(output) + ".sha256")
    # UTF-8 keeps the standard "hash  filename" format while allowing
    # operator-facing Chinese delivery filenames on Windows.
    sha_path.write_text("%s  %s\n" % (archive_sha, output.name), encoding="utf-8")
    return {
        "package": str(output),
        "sha256_file": str(sha_path),
        "sha256": archive_sha,
        "manifest": manifest,
    }


def _validated_archive_members(archive):
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_FILES:
        raise DeliveryError("交付包文件数量超过安全上限")
    total = 0
    names = set()
    for info in infos:
        name = _safe_relative_name(info.filename.rstrip("/")) if not info.is_dir() else _safe_relative_name(info.filename.rstrip("/"))
        if name in names:
            raise DeliveryError("交付包存在重复路径：%s" % name)
        names.add(name)
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise DeliveryError("交付包解压后大小超过安全上限")
        # Unix symlink marker. Windows-created ZIPs normally have mode 0 here.
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise DeliveryError("交付包不允许包含符号链接：%s" % name)
    return infos, names


def _validate_install_layout(archive, names, manifest):
    business = manifest.get("business") or {}
    price = manifest.get("price") or {}
    effect = manifest.get("effectiveness") or {}
    if business.get("target") != "data/protocol_demo.db":
        raise DeliveryError("成品数据安装目标不符合交付格式")
    if business.get("payload") != "business/product_release.iprelease.json":
        raise DeliveryError("成品数据包内路径不符合交付格式")
    if business.get("activation_policy") != "import_as_draft":
        raise DeliveryError("成品数据必须按草稿导入，交付包不能要求自动激活")

    if price.get("backend") == FORMAL_PRICE_BACKEND:
        expected_price = (
            "price/price_native_bundle.pkl",
            "services/price_service/model/price_native_bundle.pkl",
        )
    elif price.get("backend") == "portable_json":
        expected_price = ("price/price_bundle.json", "models/price_bundle.json")
    else:
        raise DeliveryError("不支持的价格模型后端：%s" % price.get("backend"))
    if (price.get("payload"), price.get("target")) != expected_price:
        raise DeliveryError("价格模型包内路径或安装目标不符合交付格式")
    if expected_price[0] not in names:
        raise DeliveryError("交付包缺少价格模型文件")

    if effect.get("backend") in FORMAL_EFFECT_BACKENDS:
        if (
            effect.get("payload_root") != "effectiveness/runtime"
            or effect.get("target") != "services/effectiveness_service/model/current"
        ):
            raise DeliveryError("正式效能运行包路径或安装目标不符合交付格式")
        runtime_manifest_name = (
            "effectiveness/runtime/effectiveness_runtime_manifest.json"
        )
        if runtime_manifest_name not in names:
            raise DeliveryError("交付包缺少正式效能运行清单")
        try:
            runtime_manifest = json.loads(
                archive.read(runtime_manifest_name).decode("utf-8-sig")
            )
        except Exception as exc:
            raise DeliveryError("正式效能运行清单不是有效 JSON：%s" % exc)
        if runtime_manifest.get("format_version") not in (
            "effectiveness-original-runtime-package-1.0",
            "effectiveness-frozen-runtime-package-1.0",
        ):
            raise DeliveryError("正式效能运行清单格式无效")
        for item in runtime_manifest.get("files") or []:
            relative = _safe_relative_name(item.get("path"))
            archive_name = "effectiveness/runtime/" + relative
            if archive_name not in names:
                raise DeliveryError("正式效能运行包缺少文件：%s" % relative)
            if _sha256_bytes(archive.read(archive_name)) != _clean(
                item.get("sha256")
            ).lower():
                raise DeliveryError("正式效能运行包内部摘要失败：%s" % relative)
    elif effect.get("backend") == "snapshot_json":
        if (
            effect.get("payload_root") != "effectiveness"
            or effect.get("target") != "models/effectiveness_bundle.json"
            or "effectiveness/effectiveness_bundle.json" not in names
        ):
            raise DeliveryError("演示效能模型路径或安装目标不符合交付格式")
    else:
        raise DeliveryError("不支持的效能模型后端：%s" % effect.get("backend"))


def verify_delivery(package, expected_sha256=None, extract_to=None):
    """Verify archive integrity and re-run the static cross-contract check."""
    package = Path(package).resolve()
    if not package.is_file():
        raise DeliveryError("交付包不存在：%s" % package)
    archive_sha = _sha256_file(package)
    if expected_sha256 and archive_sha.lower() != _clean(expected_sha256).lower():
        raise DeliveryError("交付包 SHA-256 与指定值不一致")
    try:
        archive = zipfile.ZipFile(str(package), "r")
    except Exception as exc:
        raise DeliveryError("交付包不是有效 ZIP：%s" % exc)
    with archive:
        infos, names = _validated_archive_members(archive)
        if "delivery_manifest.json" not in names:
            raise DeliveryError("交付包缺少 delivery_manifest.json")
        try:
            manifest = json.loads(archive.read("delivery_manifest.json").decode("utf-8-sig"))
        except Exception as exc:
            raise DeliveryError("交付清单不是有效 JSON：%s" % exc)
        if manifest.get("format_version") != DELIVERY_FORMAT:
            raise DeliveryError("不支持的交付包格式：%s" % manifest.get("format_version"))
        declared = manifest.get("files") or []
        declared_paths = set()
        for item in declared:
            name = _safe_relative_name(item.get("path"))
            if name in declared_paths:
                raise DeliveryError("清单重复声明文件：%s" % name)
            declared_paths.add(name)
            if name not in names:
                raise DeliveryError("交付包缺少清单文件：%s" % name)
            raw = archive.read(name)
            if len(raw) != int(item.get("size", -1)):
                raise DeliveryError("文件大小校验失败：%s" % name)
            if _sha256_bytes(raw) != _clean(item.get("sha256")).lower():
                raise DeliveryError("文件 SHA-256 校验失败：%s" % name)
        actual_payloads = set(
            info.filename for info in infos
            if not info.is_dir() and info.filename != "delivery_manifest.json"
        )
        if actual_payloads != declared_paths:
            extras = sorted(actual_payloads - declared_paths)
            missing = sorted(declared_paths - actual_payloads)
            raise DeliveryError(
                "清单与实际文件集合不一致（额外=%s，缺少=%s）" % (extras, missing)
            )
        _validate_install_layout(archive, names, manifest)
        business_path = manifest.get("business", {}).get("payload")
        if business_path not in names:
            raise DeliveryError("交付清单中的成品数据文件不存在")
        try:
            business_raw = json.loads(archive.read(business_path).decode("utf-8-sig"))
        except Exception as exc:
            raise DeliveryError("交付包内成品数据不是有效 JSON：%s" % exc)
        business_core = validate_business_release(business_raw)
        report = cross_contract_report(
            manifest.get("price", {}).get("schema") or {},
            manifest.get("effectiveness", {}).get("schema") or {},
            business_core,
        )
        if not report["valid"]:
            raise DeliveryError("交付包跨模型契约校验失败：\n- " + "\n- ".join(report["errors"]))
        expected_contract_sha = _sha256_bytes(
            _canonical_json({
                "business": business_core,
                "price_schema": manifest.get("price", {}).get("schema") or {},
                "effectiveness_schema": manifest.get("effectiveness", {}).get("schema") or {},
                "report": report,
            }).encode("utf-8")
        )
        if expected_contract_sha != manifest.get("contract_sha256"):
            raise DeliveryError("交付包契约摘要校验失败")
        if report != manifest.get("cross_contract"):
            raise DeliveryError("交付包契约报告与重新校验结果不一致")
        if _clean(manifest.get("product_code")) != business_core["product_code"]:
            raise DeliveryError("交付清单 product_code 与成品数据不一致")
        formal = (
            manifest.get("price", {}).get("backend") == FORMAL_PRICE_BACKEND
            and manifest.get("effectiveness", {}).get("backend") in FORMAL_EFFECT_BACKENDS
        )
        if bool(manifest.get("formal")) != formal:
            raise DeliveryError("交付包 formal 标记与模型后端不一致")
        if extract_to is not None:
            destination = Path(extract_to).resolve()
            destination.mkdir(parents=True, exist_ok=True)
            for info in infos:
                if info.is_dir():
                    continue
                target = destination / Path(*PurePosixPath(info.filename).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    return {"package": str(package), "sha256": archive_sha, "manifest": manifest}


def _listening_ports(host="127.0.0.1"):
    active = []
    for port in EXPECTED_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        try:
            if sock.connect_ex((host, port)) == 0:
                active.append(port)
        finally:
            sock.close()
    return active


def _ensure_services_stopped():
    active = _listening_ports()
    if active:
        raise DeliveryError(
            "安装/回滚前必须停止价格、效能和推荐服务；当前仍在监听的端口：%s"
            % "、".join(str(item) for item in active)
        )


def _project_path(project_root, relative):
    relative = _safe_relative_name(relative)
    root = Path(project_root).resolve()
    path = (root / Path(*PurePosixPath(relative).parts)).resolve()
    if path != root and root not in path.parents:
        raise DeliveryError("安装目标越出项目目录：%s" % relative)
    return path


def _copy_path(source, target):
    source, target = Path(source), Path(target)
    if source.is_dir():
        shutil.copytree(
            str(source),
            str(target),
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target))


def _remove_path(path):
    path = Path(path)
    if path.is_dir():
        shutil.rmtree(str(path))
    elif path.exists():
        path.unlink()


def _backup_sqlite(source, target):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        return False
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.execute("PRAGMA wal_checkpoint(FULL)")
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return True


def _restore_sqlite(source, target):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(target) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _import_business_draft(db_path, business_raw):
    core = validate_business_release(business_raw)
    # Keep installed drafts consistent with ProductReleaseService.import_package:
    # old packages may describe integer storage values as ``integer`` even
    # though the data center stores them as numeric values with integer search.
    data = json.loads(json.dumps(core["data"], ensure_ascii=False))
    for parameter in data.get("parameters", []):
        if _clean(parameter.get("value_type")).lower() in ("integer", "numeric"):
            parameter["value_type"] = "number"
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS product_releases(
            release_id TEXT PRIMARY KEY, product_code TEXT NOT NULL,
            product_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
            data_json TEXT NOT NULL, validation_json TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            activated_at TEXT
        )""")
        release_id = "REL-DLV-%s" % uuid.uuid4().hex[:12].upper()
        stamp = _now()
        conn.execute(
            """INSERT INTO product_releases
            (release_id,product_code,product_name,status,data_json,validation_json,created_at,updated_at)
            VALUES(?,?,?,'draft',?,NULL,?,?)""",
            (
                release_id,
                core["product_code"],
                core["product_name"],
                json.dumps(data, ensure_ascii=False),
                stamp,
                stamp,
            ),
        )
        conn.commit()
        return release_id
    finally:
        conn.close()


def _restore_from_record(project_root, backup_root, record):
    root = Path(project_root).resolve()
    for item in reversed(record.get("targets") or []):
        target = _project_path(root, item["target"])
        if item.get("kind") == "sqlite":
            if item.get("existed"):
                _restore_sqlite(backup_root / item["backup"], target)
            else:
                _remove_path(target)
            continue
        _remove_path(target)
        if item.get("existed"):
            _copy_path(backup_root / item["backup"], target)


def install_delivery(
    package,
    project_root=ROOT,
    expected_sha256=None,
    allow_demo_models=False,
    enforce_stopped=True,
    _test_fail_after=None,
):
    """Install verified models and import business data as a non-active draft."""
    if enforce_stopped:
        _ensure_services_stopped()
    project_root = Path(project_root).resolve()
    backup_parent = project_root / "backups" / "deliveries"
    backup_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="product_delivery_install_") as temp:
        extracted = Path(temp)
        verified = verify_delivery(package, expected_sha256=expected_sha256, extract_to=extracted)
        manifest = verified["manifest"]
        if not manifest.get("formal") and not allow_demo_models:
            raise DeliveryError(
                "该交付包包含演示模型，不能作为正式模型安装；"
                "如仅用于演示环境，请显式添加 --allow-demo-models"
            )
        # Keep backup paths comfortably below the legacy Windows MAX_PATH
        # boundary even when the project itself lives in a long directory.
        # The complete delivery_id remains available inside install_record.json.
        delivery_token = hashlib.sha256(
            str(manifest["delivery_id"]).encode("utf-8")
        ).hexdigest()[:12].upper()
        backup_id = "%s_%s" % (_stamp(), delivery_token)
        backup_root = backup_parent / backup_id
        backup_root.mkdir(parents=True, exist_ok=False)
        shutil.copy2(str(Path(package).resolve()), str(backup_root / "delivery_package.zip"))
        record = {
            "format_version": DELIVERY_FORMAT,
            "backup_id": backup_id,
            "delivery_id": manifest["delivery_id"],
            "product_code": manifest["product_code"],
            "package_sha256": verified["sha256"],
            "installed_at": _now(),
            "status": "installing",
            "targets": [],
            "business_release_id": None,
        }
        price_target = manifest["price"]["target"]
        effect_target = manifest["effectiveness"]["target"]
        db_target = manifest["business"]["target"]
        targets = [
            ("price", price_target),
        ]
        if manifest["price"]["backend"] == FORMAL_PRICE_BACKEND:
            targets.append(("price_sidecar", price_target + ".manifest.json"))
        targets.extend([
            ("effectiveness", effect_target),
            ("sqlite", db_target),
        ])
        try:
            for kind, relative in targets:
                target = _project_path(project_root, relative)
                backup_relative = "original/" + relative
                existed = target.exists()
                item = {
                    "kind": kind,
                    "target": relative,
                    "backup": backup_relative,
                    "existed": existed,
                }
                record["targets"].append(item)
                backup_target = backup_root / Path(*PurePosixPath(backup_relative).parts)
                if existed:
                    if kind == "sqlite":
                        _backup_sqlite(target, backup_target)
                    else:
                        backup_target.parent.mkdir(parents=True, exist_ok=True)
                        _copy_path(target, backup_target)

            price_source = extracted / Path(*PurePosixPath(manifest["price"]["payload"]).parts)
            price_destination = _project_path(project_root, price_target)
            price_destination.parent.mkdir(parents=True, exist_ok=True)
            incoming_price = price_destination.parent / (
                "." + price_destination.name + ".incoming." + uuid.uuid4().hex
            )
            shutil.copy2(str(price_source), str(incoming_price))
            os.replace(str(incoming_price), str(price_destination))
            # Native price sidecar is optional but, when included, installed too.
            price_sidecar = extracted / "price" / "price_native_bundle.pkl.manifest.json"
            sidecar_target = Path(str(price_destination) + ".manifest.json")
            if price_sidecar.is_file():
                shutil.copy2(str(price_sidecar), str(sidecar_target))
            elif manifest["price"]["backend"] == FORMAL_PRICE_BACKEND and sidecar_target.exists():
                sidecar_target.unlink()
            if _test_fail_after == "price":
                raise DeliveryError("测试注入：价格模型安装后失败")

            effect_destination = _project_path(project_root, effect_target)
            if manifest["effectiveness"]["backend"] in FORMAL_EFFECT_BACKENDS:
                effect_source = extracted / "effectiveness" / "runtime"
                incoming_effect = effect_destination.parent / (
                    "." + effect_destination.name + ".incoming." + uuid.uuid4().hex
                )
                effect_destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(effect_source), str(incoming_effect))
                previous = effect_destination.parent / (
                    "." + effect_destination.name + ".previous." + uuid.uuid4().hex
                )
                if effect_destination.exists():
                    os.replace(str(effect_destination), str(previous))
                os.replace(str(incoming_effect), str(effect_destination))
                _remove_path(previous)
            else:
                effect_source = extracted / "effectiveness" / "effectiveness_bundle.json"
                effect_destination.parent.mkdir(parents=True, exist_ok=True)
                incoming_effect = effect_destination.parent / (
                    "." + effect_destination.name + ".incoming." + uuid.uuid4().hex
                )
                shutil.copy2(str(effect_source), str(incoming_effect))
                os.replace(str(incoming_effect), str(effect_destination))
            if _test_fail_after == "effectiveness":
                raise DeliveryError("测试注入：效能模型安装后失败")

            business_payload = extracted / Path(
                *PurePosixPath(manifest["business"]["payload"]).parts
            )
            business_raw = _read_json(business_payload, "成品数据包")
            db_destination = _project_path(project_root, db_target)
            record["business_release_id"] = _import_business_draft(
                db_destination, business_raw
            )
            if _test_fail_after == "business":
                raise DeliveryError("测试注入：成品草稿导入后失败")
            record["status"] = "installed"
            record["completed_at"] = _now()
            (backup_root / "install_record.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return {
                "backup_id": backup_id,
                "backup_path": str(backup_root),
                "business_release_id": record["business_release_id"],
                "manifest": manifest,
            }
        except Exception:
            try:
                _restore_from_record(project_root, backup_root, record)
                record["status"] = "failed_rolled_back"
                record["rolled_back_at"] = _now()
            except Exception as rollback_exc:
                record["status"] = "failed_rollback_incomplete"
                record["rollback_error"] = str(rollback_exc)
            (backup_root / "install_record.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            raise


def rollback_delivery(backup_id, project_root=ROOT, enforce_stopped=True):
    """Restore the exact pre-install model files and SQLite snapshot."""
    if enforce_stopped:
        _ensure_services_stopped()
    project_root = Path(project_root).resolve()
    backup_id = _safe_relative_name(backup_id)
    if "/" in backup_id:
        raise DeliveryError("backup_id 不能包含目录")
    backup_root = project_root / "backups" / "deliveries" / backup_id
    record_path = backup_root / "install_record.json"
    if not record_path.is_file():
        raise DeliveryError("找不到安装备份记录：%s" % backup_id)
    record = _read_json(record_path, "安装备份记录")
    if record.get("status") not in ("installed", "rolled_back"):
        raise DeliveryError("当前备份记录状态不允许回滚：%s" % record.get("status"))
    safety_root = backup_root / ("rb_" + _stamp())
    safety_root.mkdir(parents=True, exist_ok=False)
    for item in record.get("targets") or []:
        current = _project_path(project_root, item["target"])
        if current.exists():
            destination = safety_root / Path(*PurePosixPath(item["target"]).parts)
            if item.get("kind") == "sqlite":
                _backup_sqlite(current, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                _copy_path(current, destination)
    _restore_from_record(project_root, backup_root, record)
    record["status"] = "rolled_back"
    record["rolled_back_at"] = _now()
    record["pre_rollback_backup"] = str(safety_root.relative_to(backup_root).as_posix())
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "backup_id": backup_id,
        "product_code": record.get("product_code"),
        "pre_rollback_backup": str(safety_root),
    }


def _print_result(result):
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def main(argv=None):
    parser = argparse.ArgumentParser(description="统一成品离线交付包工具")
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="构建统一交付包")
    build.add_argument("--price-model", required=True, help="价格原生 bundle 或演示 JSON")
    build.add_argument("--effectiveness-package", required=True, help="效能运行包目录/manifest 或演示 JSON")
    source = build.add_mutually_exclusive_group(required=True)
    source.add_argument("--business-release", help="从管理页导出的成品数据发布包")
    source.add_argument("--history-workbook", help="原始历史成品 CSV/XLSX，自动生成业务发布数据")
    build.add_argument("--product-code", help="历史表所属成品代号；默认取两个模型Schema")
    build.add_argument("--product-name", help="历史表所属成品名称；默认取效能/价格模型Schema")
    build.add_argument("--missing-tokens", default="-1,\\,/", help="历史表缺失标识，逗号分隔")
    build.add_argument("--output", required=True, help="输出 ZIP 路径")
    build.add_argument("--delivery-version")
    build.add_argument("--allow-demo-models", action="store_true")

    verify = sub.add_parser("verify", help="校验统一交付包")
    verify.add_argument("package")
    verify.add_argument("--expected-sha256")

    install = sub.add_parser("install", help="安装模型并将成品数据导入为草稿")
    install.add_argument("package")
    install.add_argument("--project-root", default=str(ROOT))
    install.add_argument("--expected-sha256")
    install.add_argument("--allow-demo-models", action="store_true")

    rollback = sub.add_parser("rollback", help="按安装备份 ID 回滚")
    rollback.add_argument("backup_id")
    rollback.add_argument("--project-root", default=str(ROOT))

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_delivery(
                args.price_model,
                args.effectiveness_package,
                args.business_release,
                args.output,
                delivery_version=args.delivery_version,
                allow_demo_models=args.allow_demo_models,
                history_workbook=args.history_workbook,
                product_code=args.product_code,
                product_name=args.product_name,
                missing_tokens=args.missing_tokens,
            )
        elif args.command == "verify":
            result = verify_delivery(args.package, expected_sha256=args.expected_sha256)
        elif args.command == "install":
            result = install_delivery(
                args.package,
                project_root=args.project_root,
                expected_sha256=args.expected_sha256,
                allow_demo_models=args.allow_demo_models,
            )
        elif args.command == "rollback":
            result = rollback_delivery(args.backup_id, project_root=args.project_root)
        else:
            parser.print_help()
            return 2
        _print_result(result)
        return 0
    except DeliveryError as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
