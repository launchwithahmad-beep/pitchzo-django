import uuid
from django.db import models
from authapp.models import Workspace, User


class Client(models.Model):
    TYPE_INDIVIDUAL = 'individual'
    TYPE_COMPANY = 'company'
    TYPE_CHOICES = [
        (TYPE_INDIVIDUAL, 'Individual'),
        (TYPE_COMPANY, 'Company'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='clients'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients_created'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_INDIVIDUAL)
    phone = models.CharField(max_length=50, blank=True, default='')
    address = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        ordering = ['name']
        unique_together = [['workspace', 'email']]

    def __str__(self):
        return self.name
