import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify


class PasswordResetOTP(models.Model):
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    reset_token = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self, minutes=15):
        return (timezone.now() - self.created_at).total_seconds() > minutes * 60


class Workspace(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspaces')

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'workspace'
            slug = base_slug
            counter = 1
            while Workspace.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Branding(models.Model):
    workspace = models.OneToOneField(
        Workspace, on_delete=models.CASCADE, related_name='branding'
    )
    logo = models.URLField(blank=True, default='')
    primaryColor = models.CharField(max_length=50, blank=True, default='')
    secondaryColor = models.CharField(max_length=50, blank=True, default='')

    def __str__(self):
        return f'Branding for {self.workspace.name}'
