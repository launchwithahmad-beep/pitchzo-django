import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.text import slugify

from pitchzo.validators import validate_image_file


def user_avatar_upload_to(instance, filename):
    ext = filename.split('.')[-1] if '.' in filename else 'png'
    return f'avatars/user_{instance.id}_{uuid.uuid4().hex[:8]}.{ext}'


class User(AbstractUser):
    """Custom User model with avatar, phone, address as part of default auth."""
    avatar = models.ImageField(
        upload_to=user_avatar_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    phone = models.CharField(max_length=50, blank=True, default='')
    address = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'auth_user'


class PasswordResetOTP(models.Model):
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    reset_token = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self, minutes=15):
        return (timezone.now() - self.created_at).total_seconds() > minutes * 60


class Workspace(models.Model):
    TYPE_INDIVIDUAL = 'individual'
    TYPE_COMPANY = 'company'
    TYPE_CHOICES = [
        (TYPE_INDIVIDUAL, 'Individual'),
        (TYPE_COMPANY, 'Company'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_INDIVIDUAL)
    phone = models.CharField(max_length=50, blank=True, default='')
    address = models.CharField(max_length=500, blank=True, default='')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspaces')
    default_template = models.ForeignKey(
        'proposalsapp.Template',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workspaces',
    )

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


def branding_logo_upload_to(instance, filename):
    ext = filename.split('.')[-1] if '.' in filename else 'png'
    return f'branding/{instance.workspace.slug}/logo_{uuid.uuid4().hex[:8]}.{ext}'


class Branding(models.Model):
    workspace = models.OneToOneField(
        Workspace, on_delete=models.CASCADE, related_name='branding'
    )
    logo = models.ImageField(
        upload_to=branding_logo_upload_to,
        blank=True,
        null=True,
        validators=[validate_image_file],
    )
    primaryColor = models.CharField(max_length=50, blank=True, default='#975EED')
    secondaryColor = models.CharField(max_length=50, blank=True, default='#86EFAC')
    tertiaryColor = models.CharField(max_length=50, blank=True, default='#93C5FD')
    name = models.CharField(max_length=255, blank=True, default='')
    companyName = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    professionalTitle = models.CharField(max_length=255, blank=True, default='')
    address = models.CharField(max_length=500, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')

    def __str__(self):
        return f'Branding for {self.workspace.name}'

    def delete(self, *args, **kwargs):
        if self.logo:
            self.logo.delete(save=False)
        super().delete(*args, **kwargs)


class UserPreferences(models.Model):
    """One-to-one with User. Deleted when user is deleted."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='GMT+5')
    time_format = models.CharField(max_length=10, default='12')  # 12 or 24
    first_day_of_week = models.CharField(max_length=20, default='monday')
    auto_sync = models.CharField(max_length=10, default='off')  # on or off
    default_workspace = models.ForeignKey(
        Workspace, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+'
    )

    def __str__(self):
        return f'Preferences for {self.user.email}'


class UserNotifications(models.Model):
    """One-to-one with User. Deleted when user is deleted."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notifications')
    new_project = models.BooleanField(default=True)   # New project alert - default active
    email = models.BooleanField(default=False)
    projects_sync = models.BooleanField(default=False)
    update = models.BooleanField(default=True)       # Update notifications - default active
    in_app = models.BooleanField(default=True)       # In-app notifications - default active

    def __str__(self):
        return f'Notifications for {self.user.email}'
