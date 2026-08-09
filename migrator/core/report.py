"""Sistema de relatórios de migração."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FileReport:
    path: str
    file_type: str
    modified: bool = False
    rules_applied: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class MigrationReport:
    timestamp: str = ""
    source_path: str = ""
    destination_path: str = ""
    mode: str = ""
    target_version: str = ""
    overlay_name: str = ""
    files_analyzed: int = 0
    files_modified: int = 0
    files_unchanged: int = 0
    files_with_errors: int = 0
    overlay_copied: int = 0
    overlay_skipped: int = 0
    total_changes: int = 0
    total_warnings: int = 0
    total_errors: int = 0
    rules_applied: dict[str, int] = field(default_factory=dict)
    file_reports: list[FileReport] = field(default_factory=list)
    global_errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def add_file_report(self, report: FileReport):
        self.file_reports.append(report)
        self.files_analyzed += 1
        if report.modified:
            self.files_modified += 1
        else:
            self.files_unchanged += 1
        if report.errors:
            self.files_with_errors += 1
        self.total_changes += len(report.changes)
        self.total_warnings += len(report.warnings)
        self.total_errors += len(report.errors)
        for rule in report.rules_applied:
            self.rules_applied[rule] = self.rules_applied.get(rule, 0) + 1

    def summary(self) -> str:
        lines = [
            f"Data: {self.timestamp}",
            f"Origem: {self.source_path}",
            f"Destino: {self.destination_path}",
        ]
        if self.target_version:
            lines.append(f"Versão de destino: {self.target_version}")
        if self.overlay_name:
            lines.append(f"Novo overlay: {self.overlay_name}")
        lines += [
            "",
            "--- Resumo ---",
            f"Arquivos analisados: {self.files_analyzed}",
            f"Arquivos atualizados (novo overlay): {self.files_modified}",
            f"Arquivos inalterados (mantidos): {self.files_unchanged}",
            f"Arquivos com erros: {self.files_with_errors}",
            f"Overlay - copiados: {self.overlay_copied}",
            f"Overlay - pulados (nao modificados): {self.overlay_skipped}",
            f"Total de alterações: {self.total_changes}",
            f"Total de avisos: {self.total_warnings}",
            f"Total de erros: {self.total_errors}",
            "",
        ]

        if self.rules_applied:
            lines.append("--- Regras Aplicadas ---")
            for rule_id, count in sorted(self.rules_applied.items()):
                lines.append(f"  {rule_id}: {count}x")
            lines.append("")

        modified_files = [r for r in self.file_reports if r.modified]
        if modified_files:
            lines.append("--- Arquivos Modificados ---")
            for report in modified_files:
                lines.append(f"\n  {report.path}")
                for change in report.changes:
                    lines.append(f"    + {change}")
                for warning in report.warnings:
                    lines.append(f"    ! {warning}")
            lines.append("")

        error_files = [r for r in self.file_reports if r.errors]
        if error_files:
            lines.append("--- Arquivos com Erros ---")
            for report in error_files:
                lines.append(f"\n  {report.path}")
                for error in report.errors:
                    lines.append(f"    X {error}")
            lines.append("")

        if self.global_errors:
            lines.append("--- Erros Globais ---")
            for error in self.global_errors:
                lines.append(f"  X {error}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)
