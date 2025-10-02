from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

class Project(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    boq_currency = models.CharField(max_length=3, default='EUR')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self) -> str:
        return self.name


class BoQCategory(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="boq_categories",
        on_delete=models.CASCADE,
    )
    sequence = models.PositiveIntegerField()
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ("sequence", "name")
        unique_together = ("project", "sequence")

    def __str__(self) -> str:
        return f"{self.project.name} - {self.sequence:02d}. {self.name}"


class BoQItem(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='boq_items')
    category = models.ForeignKey(
        'BoQCategory',
        related_name='items',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=500)
    uom = models.CharField(max_length=20)
    contract_qty = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    unit_price = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    close_note = models.TextField(blank=True)

    class Meta:
        unique_together = ('project', 'code', 'category')
        indexes = [
            models.Index(fields=['project', 'code']),
            models.Index(fields=['project', 'category', 'code']),
        ]

    def __str__(self) -> str:
        category_part = f"[{self.category.name}] " if self.category else ''
        return f"{category_part}{self.code} - {self.title}"

    def clean(self):
        if self.category and self.category.project_id != self.project_id:
            raise ValidationError('Kategorija mora pripadati istom projektu.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)




class GKSheet(models.Model):
    """
    Jedan 'list GK' = jedna SITUACIJA za jednu BoQ poziciju.
    Period je slobodan (od-do). Poravnanje i kumulativ radimo sekvencijski po poziciji.
    """
    STATUS = (
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("locked", "Locked"),  # opcionalno kasnije
    )

    project  = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="gk_sheets")
    boq_item = models.ForeignKey(BoQItem, on_delete=models.PROTECT, related_name="gk_sheets")

    # Sekvenca po BoQItem (1, 2, 3, ...) – određuje redosled i na osnovu nje sabiramo kumulativ.
    seq_no = models.PositiveIntegerField()

    # Period je informativan i slobodan
    period_from = models.DateField(null=True, blank=True)
    period_to   = models.DateField(null=True, blank=True)

    # Količina u listu i kumulativ do ovog lista (računa se)
    qty_this_period = models.DecimalField(max_digits=16, decimal_places=3, default=Decimal("0.000"))
    qty_cumulative  = models.DecimalField(max_digits=16, decimal_places=3, default=Decimal("0.000"))

    opis_izvedenih_radova = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="draft")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_gk_sheets")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            ("boq_item", "seq_no"),      # jedna sekvenca po poziciji
        )
        indexes = [
            models.Index(fields=["project", "boq_item", "seq_no"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["boq_item__code", "seq_no"]

    def __str__(self):
        return f"{self.boq_item.code} / L{self.seq_no:04d}"

    # --- Validacije domena ---
    def clean(self):
        # if self.project_id != self.boq_item.project_id:
        #     raise ValidationError("Project GK lista i BoQ stavke moraju biti isti.")
        if self.qty_this_period < 0:
            raise ValidationError("Količina u listu ne može biti negativna.")
        if self.period_from and self.period_to and self.period_from > self.period_to:
            raise ValidationError("Period FROM ne može biti posle TO.")


    def _prev_approved_sum(self) -> Decimal:
        """Suma odobrenih količina iz svih PRETHODNIH listova ove pozicije."""
        agg = GKSheet.objects.filter(
            boq_item=self.boq_item,
            status="approved",
            seq_no__lt=self.seq_no,
        ).aggregate(total=models.Sum("qty_this_period"))
        return (agg["total"] or Decimal("0.000")).quantize(Decimal("0.001"))

    def _compute_cumulative(self) -> Decimal:
        """
        Kumulativ = suma(approved prethodnih) + (ova količina ako je bar submitted/approved).
        Ako želiš da kumulativ računa isključivo odobreno, promeni uslov na self.status == "approved".
        """
        prev_sum = self._prev_approved_sum()
        include_self = self.status in ("submitted", "approved")
        return (prev_sum + (self.qty_this_period if include_self else Decimal("0.000"))).quantize(Decimal("0.001"))

    def _bounds_check(self):
        if self.qty_cumulative < 0:
            raise ValidationError("Kumulativ ne može biti negativan.")
        limit = self.boq_item.contract_qty or Decimal("0")
        if limit and self.qty_cumulative > limit:
            raise ValidationError(
                f"Kumulativ {self.qty_cumulative} prelazi ugovorenu količinu {limit} za {self.boq_item.code}."
            )

    def save(self, *args, **kwargs):
        # dodeli seq_no ako nije postavljen (next = max+1)
        if not self.seq_no:
            last = GKSheet.objects.filter(boq_item=self.boq_item).order_by("-seq_no").first()
            self.seq_no = (last.seq_no + 1) if last else 1

        self.full_clean()  # osnovne validacije
        with transaction.atomic():
            # recompute kumulativ pre snimanja
            self.qty_cumulative = self._compute_cumulative()
            self._bounds_check()
            super().save(*args, **kwargs)

    # Pomoćno zatvaranje pozicije kada kumulativ == ugovorno
    def try_close_boq_item(self, user=None, note: str = ""):
        if self.boq_item.contract_qty and self.qty_cumulative >= self.boq_item.contract_qty:
            self.boq_item.closed_at = timezone.now()
            if note: self.boq_item.close_note = note
            self.boq_item.save(update_fields=["closed_at", "close_note"])