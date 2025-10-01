# utils/boq_import.py
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple
from pathlib import Path

from django.db import transaction, models

from core.utils.boq_parser import BoQParser  # <- tvoj fajl sa BoQParser klasom
from core.models import Project, BoQCategory, BoQItem  # prilagodi putanju do modela


def _q(v, qexp: str) -> Decimal:
    """
    Kvantizacija sa HALF_UP (npr. 2.345 -> 2.345; 2.3456 -> 2.346 za qexp='0.001').
    Ako je None, vrati 0.
    """
    if v is None:
        v = Decimal("0")
    if not isinstance(v, Decimal):
        v = Decimal(str(v))
    return v.quantize(Decimal(qexp), rounding=ROUND_HALF_UP)


def import_boq_excel(
    *,
    project: Project,
    excel_path: Path | str,
    clear_existing: bool = False,
    batch_size: int = 1000,
) -> Dict[str, object]:
    """
    Učita BoQ iz Excel-a i upiše u bazu za dati Project.

    - Svaki sheet -> BoQCategory (sequence po redosledu sheet-ova, name = sheet/discipline).
    - Svaka pozicija -> BoQItem (code=position_id, title=description, uom=unit,
      contract_qty=quantity (3 dec), unit_price=unit_price (2 dec)).

    Ako je clear_existing=True, pre importa briše sve stavke i kategorije za projekat.
    Vraća dict sa statistikama i upozorenjima parser-a.
    """
    excel_path = Path(excel_path)

    parser = BoQParser()
    results = parser.parse_workbook(excel_path)  # List[DisciplineResult]

    # Skupi sva parser upozorenja (po sheetovima)
    warnings: List[str] = []
    for r in results:
        if r.warnings:
            warnings.extend([f"[{r.sheet_name}] {w}" for w in r.warnings])

    with transaction.atomic():
        if clear_existing:
            BoQItem.objects.filter(project=project).delete()
            BoQCategory.objects.filter(project=project).delete()

        # 1) Kategorije po redosledu sheet-ova (sequence kreće od 1)
        seq_to_cat: Dict[int, BoQCategory] = {}
        for idx, r in enumerate(results, start=1):
            cat, created = BoQCategory.objects.get_or_create(
                project=project,
                sequence=idx,
                defaults={"name": r.discipline or r.sheet_name or f"Sheet {idx}"},
            )
            # ako ime nije isto, osveži (npr. preimenovan sheet)
            desired_name = r.discipline or r.sheet_name or f"Sheet {idx}"
            if cat.name != desired_name:
                cat.name = desired_name
                cat.save(update_fields=["name"])
            seq_to_cat[idx] = cat

        # 2) Priprema postojećih item-a za upsert
        existing_items = {
            (it.project_id, it.code): it
            for it in BoQItem.objects.filter(project=project).only(
                "id", "project_id", "code", "title", "uom", "contract_qty", "unit_price", "category_id"
            )
        }

        to_create: List[BoQItem] = []
        to_update: List[BoQItem] = []

        created_count = 0
        updated_count = 0
        skipped_count = 0

        # 3) Prođi kroz rezultate i pripremi BoQItem-e
        for seq, r in enumerate(results, start=1):
            cat = seq_to_cat[seq]
            for pos in r.positions:
                code = (pos.position_id or "").strip()
                title = (pos.description or "").strip()
                uom = (pos.unit or "").strip()

                if not code:
                    skipped_count += 1
                    continue

                qty = _q(pos.quantity, "0.001")
                unit_price = _q(pos.unit_price, "0.01")

                key = (project.id, code)
                if key in existing_items:
                    obj = existing_items[key]
                    # ažuriraj samo ako ima promena (mikro optimizacija)
                    changed = False
                    if obj.title != title:
                        obj.title = title; changed = True
                    if obj.uom != uom:
                        obj.uom = uom; changed = True
                    if obj.contract_qty != qty:
                        obj.contract_qty = qty; changed = True
                    if obj.unit_price != unit_price:
                        obj.unit_price = unit_price; changed = True
                    if obj.category_id != cat.id:
                        obj.category_id = cat.id; changed = True
                    if changed:
                        to_update.append(obj)
                else:
                    to_create.append(
                        BoQItem(
                            project=project,
                            category=cat,
                            code=code,
                            title=title,
                            uom=uom,
                            contract_qty=qty,
                            unit_price=unit_price,
                        )
                    )

        # 4) Bulk create/update
        for i in range(0, len(to_create), batch_size):
            BoQItem.objects.bulk_create(to_create[i:i + batch_size])
            created_count += len(to_create[i:i + batch_size])

        if to_update:
            BoQItem.objects.bulk_update(
                to_update,
                ["title", "uom", "contract_qty", "unit_price", "category"],
                batch_size=batch_size,
            )
            updated_count = len(to_update)

    return {
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "categories": len(results),
        "warnings": warnings,
    }
