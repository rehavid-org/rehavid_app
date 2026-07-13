from django.db import models


class Plan(models.Model):
    """Plan de acción, creado a mano o desde un finding del motor de recomendaciones."""

    class Estado(models.TextChoices):
        ABIERTO = "open", "Abierto"
        EN_RIESGO = "risk", "En riesgo"
        COMPLETADO = "done", "Completado"

    codigo = models.CharField("código", max_length=20, unique=True, blank=True)  # PL-001
    area = models.CharField("área", max_length=60)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    responsable = models.CharField(max_length=120)
    vence = models.DateField()
    avance = models.PositiveIntegerField(default=0, help_text="Porcentaje 0-100")
    esperado = models.PositiveIntegerField(default=0, help_text="Porcentaje esperado a hoy")
    estado = models.CharField(
        max_length=8,
        choices=Estado.choices,
        default=Estado.ABIERTO,
        db_index=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["vence"]
        verbose_name = "plan de acción"
        verbose_name_plural = "planes de acción"

    def __str__(self):
        return f"{self.codigo} · {self.titulo}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.codigo:
            self.codigo = f"PL-{self.pk:03d}"
            super().save(update_fields=["codigo"])
