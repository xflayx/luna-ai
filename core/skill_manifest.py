from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _norm_text(value: Any) -> str:
    texto = str(value or "").strip().lower()
    return texto


def _norm_list(values: Any) -> tuple[str, ...]:
    if not values:
        return ()
    itens: list[str] = []
    for value in values:
        texto = _norm_text(value)
        if texto and texto not in itens:
            itens.append(texto)
    return tuple(itens)


@dataclass(frozen=True)
class SkillPort:
    id: str
    type: str = "string"
    description: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SkillPort":
        if not data:
            return cls(id="")
        return cls(
            id=str(data.get("id", "")).strip(),
            type=str(data.get("type", "string")).strip() or "string",
            description=str(data.get("description", "")).strip(),
        )


@dataclass(frozen=True)
class SkillConfigField:
    type: str = "string"
    label: str = ""
    description: str = ""
    required: bool = False
    default: Any = None
    options: tuple[Any, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SkillConfigField":
        if not data:
            return cls()
        options = data.get("options") or ()
        if isinstance(options, list):
            options = tuple(options)
        return cls(
            type=str(data.get("type", "string")).strip() or "string",
            label=str(data.get("label", "")).strip(),
            description=str(data.get("description", "")).strip(),
            required=bool(data.get("required", False)),
            default=data.get("default"),
            options=tuple(options) if isinstance(options, tuple) else (),
        )


@dataclass(frozen=True)
class SkillManifest:
    id: str
    nome: str
    descricao: str = ""
    versao: str = "1.0.0"
    autor: str = ""
    intents: tuple[str, ...] = ()
    gatilhos: tuple[str, ...] = ()
    inputs: tuple[SkillPort, ...] = ()
    outputs: tuple[SkillPort, ...] = ()
    config: dict[str, SkillConfigField] = field(default_factory=dict)
    category: str = "general"

    def matches_intent(self, intent: str | None) -> bool:
        if not intent:
            return False
        return _norm_text(intent) in self.intents

    def matches_command(self, cmd_limpo: str) -> bool:
        texto = _norm_text(cmd_limpo)
        if not texto:
            return False
        return any(g in texto for g in self.gatilhos)

    @classmethod
    def from_sources(
        cls,
        *,
        module_name: str,
        skill_info: Mapping[str, Any] | None = None,
        gatilhos: Any = None,
        manifest_data: Mapping[str, Any] | None = None,
    ) -> "SkillManifest":
        skill_info = skill_info or {}
        manifest_data = manifest_data or {}

        nome = (
            str(manifest_data.get("name", "")).strip()
            or str(skill_info.get("nome", "")).strip()
            or module_name
        )
        description = (
            str(manifest_data.get("description", "")).strip()
            or str(skill_info.get("descricao", "")).strip()
        )
        version = (
            str(manifest_data.get("version", "")).strip()
            or str(skill_info.get("versao", "")).strip()
            or "1.0.0"
        )
        author = (
            str(manifest_data.get("author", "")).strip()
            or str(skill_info.get("autor", "")).strip()
        )
        category = str(manifest_data.get("category", "general")).strip() or "general"

        intents = _norm_list(manifest_data.get("intents") or skill_info.get("intents"))
        gatilhos_norm = _norm_list(manifest_data.get("gatilhos") or gatilhos)

        inputs_raw = manifest_data.get("inputs") or ()
        outputs_raw = manifest_data.get("outputs") or ()
        inputs = tuple(
            SkillPort.from_dict(item)
            for item in inputs_raw
            if isinstance(item, Mapping)
        )
        outputs = tuple(
            SkillPort.from_dict(item)
            for item in outputs_raw
            if isinstance(item, Mapping)
        )

        config_raw = manifest_data.get("config") or {}
        config: dict[str, SkillConfigField] = {}
        if isinstance(config_raw, Mapping):
            for key, value in config_raw.items():
                if not isinstance(key, str):
                    continue
                if not isinstance(value, Mapping):
                    continue
                config[key] = SkillConfigField.from_dict(value)

        return cls(
            id=module_name,
            nome=nome,
            descricao=description,
            versao=version,
            autor=author,
            intents=intents,
            gatilhos=gatilhos_norm,
            inputs=inputs,
            outputs=outputs,
            config=config,
            category=category,
        )
