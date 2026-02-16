from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Optional

from core.skill_manifest import SkillManifest


logger = logging.getLogger("SkillRegistry")
_UTF8_CONSOLE_READY = False


def _ensure_console_utf8() -> None:
    global _UTF8_CONSOLE_READY
    if _UTF8_CONSOLE_READY:
        return
    if os.getenv("LUNA_FORCE_UTF8_CONSOLE", "1") != "1":
        _UTF8_CONSOLE_READY = True
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue
    _UTF8_CONSOLE_READY = True


@dataclass
class SkillEntry:
    module_name: str
    module: Any | None = None
    manifest: SkillManifest | None = None
    last_error: str = ""
    manifest_source: str = ""
    has_external_manifest: bool = False
    validation_errors: tuple[str, ...] = ()

    @property
    def loaded(self) -> bool:
        return self.module is not None and self.manifest is not None


class SkillRegistry:
    def __init__(self, base_dir: str | None = None, skills_package: str = "skills"):
        if base_dir:
            self._base_dir = base_dir
        else:
            self._base_dir = os.path.dirname(os.path.dirname(__file__))
        self._skills_package = skills_package
        self._skills_dir = os.path.join(self._base_dir, "skills")
        self._entries: dict[str, SkillEntry] = {}
        self._ignored_files = {"__init__.py", "conversa1.py", "vision1.py"}

    def discover(self) -> list[str]:
        if not os.path.isdir(self._skills_dir):
            logger.warning("Diretorio de skills nao encontrado: %s", self._skills_dir)
            return []

        modules: list[str] = []
        for filename in os.listdir(self._skills_dir):
            if not filename.endswith(".py"):
                continue
            if filename in self._ignored_files:
                continue
            if filename.startswith("_"):
                continue
            modules.append(filename[:-3])
        modules.sort()

        active = set(modules)
        for module_name in list(self._entries.keys()):
            if module_name not in active:
                self._entries.pop(module_name, None)

        for module_name in modules:
            self._entries.setdefault(module_name, SkillEntry(module_name=module_name))
        return modules

    def list_skill_names(self) -> list[str]:
        if not self._entries:
            self.discover()
        return sorted(self._entries.keys())

    def get_entry(self, module_name: str) -> Optional[SkillEntry]:
        return self._entries.get(module_name)

    def load(self, module_name: str) -> Optional[SkillEntry]:
        entry = self._entries.setdefault(module_name, SkillEntry(module_name=module_name))
        if entry.loaded:
            return entry
        try:
            mod = importlib.import_module(f"{self._skills_package}.{module_name}")
            manifest, manifest_source, has_external_manifest = self._build_manifest(module_name, mod)
            ok, errors = self._validate_skill(module_name, mod, manifest)
            if not ok:
                entry.module = None
                entry.manifest = None
                entry.validation_errors = tuple(errors)
                entry.manifest_source = manifest_source
                entry.has_external_manifest = has_external_manifest
                entry.last_error = "; ".join(errors) or "Skill invalida"
                return None
            if hasattr(mod, "inicializar"):
                try:
                    _ensure_console_utf8()
                    mod.inicializar()
                except Exception as exc:
                    logger.warning(
                        "Falha nao-bloqueante em inicializar() da skill %s: %s",
                        module_name,
                        exc,
                    )
            entry.module = mod
            entry.manifest = manifest
            entry.last_error = ""
            entry.manifest_source = manifest_source
            entry.has_external_manifest = has_external_manifest
            entry.validation_errors = ()
            return entry
        except Exception as exc:
            entry.module = None
            entry.manifest = None
            entry.manifest_source = ""
            entry.has_external_manifest = bool(self._existing_manifest_file(module_name))
            entry.validation_errors = ()
            entry.last_error = str(exc)
            logger.error("Falha ao carregar skill %s: %s", module_name, exc)
            return None

    def reload(self, module_name: str) -> Optional[SkillEntry]:
        entry = self._entries.setdefault(module_name, SkillEntry(module_name=module_name))
        try:
            mod = importlib.import_module(f"{self._skills_package}.{module_name}")
            mod = importlib.reload(mod)
            manifest, manifest_source, has_external_manifest = self._build_manifest(module_name, mod)
            ok, errors = self._validate_skill(module_name, mod, manifest)
            if not ok:
                entry.module = None
                entry.manifest = None
                entry.validation_errors = tuple(errors)
                entry.manifest_source = manifest_source
                entry.has_external_manifest = has_external_manifest
                entry.last_error = "; ".join(errors) or "Skill invalida"
                return None
            if hasattr(mod, "inicializar"):
                try:
                    _ensure_console_utf8()
                    mod.inicializar()
                except Exception as exc:
                    logger.warning(
                        "Falha nao-bloqueante em inicializar() da skill %s: %s",
                        module_name,
                        exc,
                    )
            entry.module = mod
            entry.manifest = manifest
            entry.last_error = ""
            entry.manifest_source = manifest_source
            entry.has_external_manifest = has_external_manifest
            entry.validation_errors = ()
            return entry
        except Exception as exc:
            entry.module = None
            entry.manifest = None
            entry.manifest_source = ""
            entry.has_external_manifest = bool(self._existing_manifest_file(module_name))
            entry.validation_errors = ()
            entry.last_error = str(exc)
            logger.error("Falha ao recarregar skill %s: %s", module_name, exc)
            return None

    def reload_all(self) -> int:
        self.discover()
        count = 0
        for module_name in self.list_skill_names():
            if self.reload(module_name):
                count += 1
        return count

    def candidates_by_intent(self, intent: str | None) -> list[str]:
        if not intent:
            return []
        selected: list[str] = []
        for module_name in self.list_skill_names():
            entry = self.load(module_name)
            if not entry or not entry.manifest:
                continue
            if entry.manifest.matches_intent(intent):
                selected.append(module_name)
        return selected

    def candidates_by_trigger(self, cmd_limpo: str) -> list[str]:
        selected: list[str] = []
        for module_name in self.list_skill_names():
            entry = self.load(module_name)
            if not entry or not entry.manifest:
                continue
            if entry.manifest.matches_command(cmd_limpo):
                selected.append(module_name)
        return selected

    def get_manifest(self, module_name: str) -> Optional[SkillManifest]:
        entry = self.load(module_name)
        if not entry:
            return None
        return entry.manifest

    def get_manifest_coverage(self) -> dict[str, Any]:
        self.discover()
        skills: list[dict[str, Any]] = []
        missing: list[str] = []
        with_external = 0
        for module_name in self.list_skill_names():
            manifest_path = self._existing_manifest_file(module_name)
            has_external = bool(manifest_path)
            if has_external:
                with_external += 1
            else:
                missing.append(module_name)
            entry = self._entries.get(module_name)
            skills.append(
                {
                    "module": module_name,
                    "has_external_manifest": has_external,
                    "manifest_path": manifest_path,
                    "loaded": bool(entry and entry.loaded),
                    "last_error": (entry.last_error if entry else ""),
                    "manifest_source": (entry.manifest_source if entry else ""),
                }
            )
        total = len(skills)
        return {
            "total_skills": total,
            "with_external_manifest": with_external,
            "without_external_manifest": total - with_external,
            "missing_external_manifests": sorted(missing),
            "skills": skills,
        }

    def get_diagnostics(self, ensure_loaded: bool = False) -> dict[str, Any]:
        self.discover()
        diagnostics: list[dict[str, Any]] = []
        for module_name in self.list_skill_names():
            entry = self._entries.setdefault(module_name, SkillEntry(module_name=module_name))
            if ensure_loaded:
                self.load(module_name)
                entry = self._entries.get(module_name) or entry

            diagnostics.append(
                {
                    "module": module_name,
                    "loaded": entry.loaded,
                    "manifest_source": entry.manifest_source,
                    "has_external_manifest": entry.has_external_manifest,
                    "validation_errors": list(entry.validation_errors),
                    "last_error": entry.last_error,
                }
            )
        loaded = len([d for d in diagnostics if d["loaded"]])
        failed = len([d for d in diagnostics if d["last_error"]])
        return {
            "total": len(diagnostics),
            "loaded": loaded,
            "failed": failed,
            "entries": diagnostics,
        }

    def _validate_skill(
        self,
        module_name: str,
        mod: Any,
        manifest: SkillManifest | None,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not hasattr(mod, "executar"):
            errors.append("Skill sem executar().")
        if not callable(getattr(mod, "executar", None)):
            errors.append("Skill executar nao e chamavel.")
        if manifest is None:
            errors.append("Manifesto invalido ou ausente.")
            return False, errors

        expected_id = module_name.strip().lower()
        if not manifest.id:
            errors.append("Manifesto sem id.")
        elif manifest.id.strip().lower() != expected_id:
            errors.append(
                f"Manifesto id '{manifest.id}' nao corresponde ao modulo '{module_name}'."
            )

        if not manifest.nome:
            errors.append("Manifesto sem nome.")

        if not manifest.intents and not manifest.gatilhos:
            errors.append("Manifesto sem intents e sem gatilhos.")

        allowed_config_types = {"string", "number", "boolean", "select", "textarea"}
        for field_name, field in manifest.config.items():
            if not field_name.strip():
                errors.append("Campo de config com chave vazia.")
                continue
            if field.type not in allowed_config_types:
                errors.append(
                    f"Config '{field_name}' com tipo invalido '{field.type}'."
                )

        for port in (*manifest.inputs, *manifest.outputs):
            if not port.id:
                errors.append("Porta de manifesto sem id.")
                break

        if errors:
            logger.warning(
                "Validacao de skill falhou para %s: %s",
                module_name,
                "; ".join(errors),
            )
            return False, errors
        return True, []

    def _build_manifest(self, module_name: str, mod: Any) -> tuple[SkillManifest, str, bool]:
        manifest_data, manifest_path = self._load_manifest_file(module_name)
        source_parts: list[str] = []
        if manifest_path:
            source_parts.append("file")
        embedded_manifest = getattr(mod, "SKILL_MANIFEST", None)
        if isinstance(embedded_manifest, dict):
            merged = dict(manifest_data)
            merged.update(embedded_manifest)
            manifest_data = merged
            source_parts.append("embedded")

        skill_info = getattr(mod, "SKILL_INFO", None)
        gatilhos = getattr(mod, "GATILHOS", None)
        manifest = SkillManifest.from_sources(
            module_name=module_name,
            skill_info=skill_info if isinstance(skill_info, dict) else {},
            gatilhos=gatilhos,
            manifest_data=manifest_data,
        )
        manifest_source = "+".join(source_parts) if source_parts else "legacy_fallback"
        has_external_manifest = bool(manifest_path)
        return manifest, manifest_source, has_external_manifest

    def _manifest_candidates(self, module_name: str) -> tuple[str, ...]:
        return (
            os.path.join(self._skills_dir, f"{module_name}.manifest.json"),
            os.path.join(self._skills_dir, "manifests", f"{module_name}.json"),
        )

    def _existing_manifest_file(self, module_name: str) -> str:
        for path in self._manifest_candidates(module_name):
            if not os.path.isfile(path):
                continue
            return path
        return ""

    def _load_manifest_file(self, module_name: str) -> tuple[dict[str, Any], str]:
        manifest_path = self._existing_manifest_file(module_name)
        if not manifest_path:
            return {}, ""
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise ValueError(f"Manifesto JSON invalido em {manifest_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Manifesto deve ser objeto JSON: {manifest_path}")
        return data, manifest_path

    # Compat helper para outros pontos do codigo.
    def has_external_manifest(self, module_name: str) -> bool:
        return bool(self._existing_manifest_file(module_name))

    # Compat helper para listagem direta.
    def list_missing_external_manifests(self) -> list[str]:
        self.discover()
        missing: list[str] = []
        for module_name in self.list_skill_names():
            if not self._existing_manifest_file(module_name):
                missing.append(module_name)
        return sorted(missing)

    def load_manifest_raw(self, module_name: str) -> dict[str, Any]:
        data, _ = self._load_manifest_file(module_name)
        return data
