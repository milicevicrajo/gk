from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class BoQItem(models.Model):
    project = models.ForeignKey(
        Project,
        related_name="boq_items",
        on_delete=models.CASCADE,
    )
    code = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    unit_of_measure = models.CharField(max_length=20)
    contracted_quantity = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("project", "code")
        ordering = ["project", "code"]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.code}"


class GKSheet(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    project = models.ForeignKey(
        Project,
        related_name="sheets",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    date = models.DateField()
    note = models.TextField(blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "project"]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.date:%Y-%m-%d} ({self.get_status_display()})"


class GKEntry(models.Model):
    sheet = models.ForeignKey(
        GKSheet,
        related_name="entries",
        on_delete=models.CASCADE,
    )
    boq_item = models.ForeignKey(
        BoQItem,
        related_name="entries",
        on_delete=models.PROTECT,
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = ("sheet", "boq_item")

    def __str__(self) -> str:
        return f"{self.sheet} / {self.boq_item.code}"


class ReviewToken(models.Model):
    class TokenType(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"

    sheet = models.ForeignKey(
        GKSheet,
        related_name="review_tokens",
        on_delete=models.CASCADE,
    )
    token = models.CharField(max_length=255, unique=True)
    token_type = models.CharField(max_length=7, choices=TokenType.choices)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-expires_at"]

    def __str__(self) -> str:
        return f"{self.get_token_type_display()} for {self.sheet}"

