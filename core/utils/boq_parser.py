"""Domain-specific parser for extracting Bill of Quantities (BoQ) data."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

COLUMN_VARIANTS: Dict[str, Sequence[str]] = {
    "position_id": (
        "redni broj",
        "r.br",
        "r. br.",
        "rb",
        "r-b",
        "red. br.",
        "pozicija",
        "poz.",
        "poz",
        "item no",
        "item",
        "no",
        "№",
        "бр.",
        "редни број",
        "ред. бр.",
        "поз.",
        "позиција",
    ),
    "description": (
        "opis",
        "opis radova",
        "naziv",
        "naziv radova",
        "radovi",
        "description",
        "desc",
        "item description",
        "опис",
        "опис радова",
        "назив",
    ),
    "unit": (
        "jm",
        "jedinica",
        "jedinica mere",
        "jed. mera",
        "jed. m.",
        "j.m.",
        "unit",
        "uom",
        "јединица",
        "јед. мера",
        "јм",
    ),
    "quantity": (
        "količina",
        "kol.",
        "količ.",
        "količina [jm]",
        "qty",
        "quantity",
        "количина",
        "кол.",
    ),
    "unit_price": (
        "jedinična cena",
        "jed. cena",
        "jed.čena",
        "jedinicna cena",
        "jc",
        "cena/jm",
        "unit price",
        "rate",
        "јединична цена",
        "јед. цена",
    ),
    "total_price": (
        "iznos",
        "ukupno",
        "vrednost",
        "amount",
        "total",
        "subtotal",
        "сума",
        "износ",
        "укупно",
        "вредност",
    ),
}

ALLOWED_UNITS = {
    "m",
    "m2",
    "m3",
    "kg",
    "t",
    "kom",
    "set",
    "par",
    "dan",
    "h",
    "č",
    "km",
    "l",
    "kwh",
    "g",
    "pak",
    "rol",
    "pal",
    "voz",
    "sat",
    "mes",
    "god",
}

POSITION_PATTERN = re.compile(r"^\d+(?:[.\-]\d+)*$")
TOTAL_MARKERS = {"ukupno", "sum", "zbir", "total"}
NUMERIC_RE = re.compile(r"-?\d+[\d.,]*")


@dataclass
class ColumnMapping:
    position_id: int
    description: int
    unit: int
    quantity: int
    unit_price: int
    total_price: int


@dataclass
class BoQPosition:
    discipline: str
    position_id: str
    description: str
    unit: str
    quantity: Optional[Decimal]
    unit_price: Optional[Decimal]
    total_price: Optional[Decimal]
    source_row_indices: List[int] = field(default_factory=list)
    computed_total: Optional[Decimal] = None
    total_matches: bool = True

    def to_dict(self) -> Dict[str, object]:
        quantity = float(self.quantity) if self.quantity is not None else 0.0
        unit_price = float(self.unit_price) if self.unit_price is not None else 0.0
        total_price = float(self.total_price) if self.total_price is not None else 0.0
        payload = {
            "discipline": self.discipline,
            "position_id": self.position_id,
            "description": self.description,
            "unit": self.unit,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price,
        }
        if not self.total_matches and self.computed_total is not None:
            payload["computed_total"] = float(self.computed_total)
        return payload


@dataclass
class DisciplineResult:
    discipline: str
    sheet_name: str
    positions: List[BoQPosition]
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "discipline": self.discipline,
            "sheet_name": self.sheet_name,
            "positions": [pos.to_dict() for pos in self.positions],
            "warnings": self.warnings,
        }


def normalize_header_value(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("²", "2").replace("³", "3")
    return text


def find_header_row(df: pd.DataFrame) -> Optional[int]:
    best_idx: Optional[int] = None
    best_score = 0
    for idx, row in df.iterrows():
        normalized = [normalize_header_value(cell) for cell in row]
        non_empty = sum(1 for cell in normalized if cell)
        if non_empty < 3:
            continue
        score = 0
        for cell in normalized:
            for variants in COLUMN_VARIANTS.values():
                if cell in variants:
                    score += 2
            if cell in ALLOWED_UNITS:
                score += 1
        if score > best_score:
            best_score = score
            best_idx = idx
        if score >= 4:
            break
    return best_idx


def match_columns_by_name(headers: Sequence[str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for idx, header in enumerate(headers):
        normalized = normalize_header_value(header)
        if not normalized:
            continue
        for category, variants in COLUMN_VARIANTS.items():
            if normalized in variants and category not in mapping:
                mapping[category] = idx
    return mapping


def column_contains_units(series: pd.Series) -> int:
    count = 0
    for value in series:
        token = normalize_header_value(value)
        if token in ALLOWED_UNITS:
            count += 1
    return count


def infer_columns_structurally(df: pd.DataFrame, header_idx: int, mapping: Dict[str, int]) -> ColumnMapping:
    data = df.iloc[header_idx + 1 :]
    if "unit" not in mapping:
        unit_scores = {
            col: column_contains_units(data.iloc[:, col]) for col in range(df.shape[1])
        }
        unit_col = max(unit_scores, key=unit_scores.get)
        mapping["unit"] = unit_col
    if "quantity" not in mapping:
        candidate = mapping["unit"] - 1 if mapping["unit"] > 0 else mapping["unit"]
        mapping["quantity"] = max(0, candidate)
    if "total_price" not in mapping:
        candidate = mapping["unit"] + 1
        if candidate < df.shape[1]:
            mapping["total_price"] = candidate
        else:
            mapping["total_price"] = mapping["unit"]
    if "unit_price" not in mapping:
        potential = mapping["quantity"] + 1
        if potential != mapping.get("unit"):
            mapping["unit_price"] = min(potential, df.shape[1] - 1)
        else:
            mapping["unit_price"] = mapping["unit"]
    if "position_id" not in mapping:
        best_col = 0
        best_hits = -1
        for col in range(df.shape[1]):
            hits = 0
            for value in data.iloc[:, col]:
                text = normalize_header_value(value)
                if POSITION_PATTERN.match(text):
                    hits += 1
            if hits > best_hits:
                best_hits = hits
                best_col = col
        mapping["position_id"] = best_col
    if "description" not in mapping:
        best_col = mapping["position_id"] + 1
        mapping["description"] = min(best_col, df.shape[1] - 1)

    return ColumnMapping(
        position_id=mapping["position_id"],
        description=mapping["description"],
        unit=mapping["unit"],
        quantity=mapping["quantity"],
        unit_price=mapping["unit_price"],
        total_price=mapping["total_price"],
    )


def parse_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\u00a0", " ")
    match = NUMERIC_RE.search(text)
    if not match:
        return None
    number = match.group(0).replace(".", "").replace(",", ".")
    try:
        return Decimal(number)
    except InvalidOperation:
        return None


def is_total_row(values: Sequence[object]) -> bool:
    for value in values:
        text = normalize_header_value(value)
        if any(marker in text for marker in TOTAL_MARKERS):
            return True
    return False


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"nan", "none", "null"}:
        return ""
    return text


def parse_positions(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    header_idx: int,
    discipline: str,
) -> Tuple[List[BoQPosition], List[str]]:
    positions: List[BoQPosition] = []
    warnings: List[str] = []
    current: Optional[BoQPosition] = None
    description_parts: List[str] = []

    for rel_idx, (_, row) in enumerate(df.iloc[header_idx + 1 :].iterrows(), start=header_idx + 1):
        row_values = row.tolist()
        if is_total_row(row_values):
            continue

        raw_id = clean_text(row.iloc[mapping.position_id])
        desc_fragment = clean_text(row.iloc[mapping.description])
        unit_token = normalize_header_value(row.iloc[mapping.unit]) if mapping.unit < len(row) else ""
        quantity = parse_decimal(row.iloc[mapping.quantity]) if mapping.quantity < len(row) else None
        unit_price = parse_decimal(row.iloc[mapping.unit_price]) if mapping.unit_price < len(row) else None
        total_price = parse_decimal(row.iloc[mapping.total_price]) if mapping.total_price < len(row) else None

        is_new_item = bool(raw_id)

        if is_new_item:
            if current:
                current.description = " ".join(filter(None, description_parts)).strip()
                if current.description == "":
                    warnings.append(
                        f"Sheet {discipline}: missing description for position {current.position_id}"
                    )
                enforce_numeric_integrity(current, warnings)
                positions.append(current)
            description_parts = []
            current = BoQPosition(
                discipline=discipline,
                position_id=raw_id,
                description="",
                unit="",
                quantity=None,
                unit_price=None,
                total_price=None,
                source_row_indices=[rel_idx],
            )

        if current is None:
            continue

        current.source_row_indices.append(rel_idx)
        if desc_fragment:
            description_parts.append(desc_fragment)

        if unit_token and unit_token in ALLOWED_UNITS and not current.unit:
            current.unit = unit_token

        if quantity is not None and (current.quantity is None or current.quantity == Decimal(0)):
            current.quantity = quantity

        if unit_price is not None and (current.unit_price is None or current.unit_price == Decimal(0)):
            current.unit_price = unit_price

        if total_price is not None and (current.total_price is None or current.total_price == Decimal(0)):
            current.total_price = total_price

    if current:
        current.description = " ".join(filter(None, description_parts)).strip()
        if current.description == "":
            warnings.append(
                f"Sheet {discipline}: missing description for position {current.position_id}"
            )
        enforce_numeric_integrity(current, warnings)
        positions.append(current)

    return positions, warnings


def enforce_numeric_integrity(position: BoQPosition, warnings: List[str]) -> None:
    quantity = position.quantity if position.quantity is not None else Decimal(0)
    unit_price = position.unit_price if position.unit_price is not None else Decimal(0)
    computed = quantity * unit_price
    position.computed_total = computed

    if position.total_price is None or position.total_price == Decimal(0):
        position.total_price = computed
        position.total_matches = True
    else:
        if position.total_price.is_nan():
            position.total_price = computed
            position.total_matches = True
        else:
            difference = abs(position.total_price - computed)
            try:
                position.total_matches = difference <= Decimal("0.01")
            except InvalidOperation:
                position.total_matches = False
                warnings.append(
                    f"Position {position.position_id} total comparison failed (difference={difference})"
                )
                return
            if not position.total_matches:
                warnings.append(
                    f"Position {position.position_id} total mismatch: source={position.total_price} computed={computed}"
                )

    if position.quantity is None:
        warnings.append(f"Position {position.position_id} missing quantity")
    if position.unit_price is None:
        warnings.append(f"Position {position.position_id} missing unit price")
    if not position.unit:
        warnings.append(f"Position {position.position_id} missing unit of measure")


class BoQParser:
    """High-level API for extracting BoQ data from Excel files."""

    def parse_workbook(self, path: Path) -> List[DisciplineResult]:
        excel = pd.ExcelFile(path)
        results: List[DisciplineResult] = []
        for sheet_name in excel.sheet_names:
            raw_df = excel.parse(sheet_name=sheet_name, header=None)
            discipline = sheet_name.strip()
            header_idx = find_header_row(raw_df)
            if header_idx is None:
                results.append(
                    DisciplineResult(
                        discipline=discipline,
                        sheet_name=sheet_name,
                        positions=[],
                        warnings=["Header row could not be detected"],
                    )
                )
                continue
            headers = raw_df.iloc[header_idx].tolist()
            mapping = match_columns_by_name(headers)
            colmap = infer_columns_structurally(raw_df, header_idx, mapping)
            positions, warns = parse_positions(raw_df, colmap, header_idx, discipline)
            results.append(
                DisciplineResult(
                    discipline=discipline,
                    sheet_name=sheet_name,
                    positions=positions,
                    warnings=warns,
                )
            )
        return results

