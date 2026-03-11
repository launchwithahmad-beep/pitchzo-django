import random
import string
import uuid
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from pitchzo.validators import validate_image_file, validation_error_message
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Workspace, Branding, PasswordResetOTP, UserPreferences, UserNotifications, User


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


# --- Auth views (AllowAny) ---

@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    data = request.data
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()

    if not email or not password:
        return Response(
            {'error': 'email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    email_lower = email.lower().strip()
    if User.objects.filter(email=email_lower).exists():
        return Response(
            {'error': 'email already registered'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if User.objects.filter(username=email_lower).exists():
        return Response(
            {'error': 'email already registered'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.create_user(
        username=email_lower,
        email=email_lower,
        password=password,
        first_name=first_name,
        last_name=last_name
    )

    # Create default individual workspace and branding for new user
    workspace_name = f"{first_name} {last_name}".strip() or email_lower.split("@")[0]
    workspace = Workspace.objects.create(name=workspace_name, owner=user)
    create_branding_for_workspace(workspace, user)

    # Create preferences and notifications for new user
    UserPreferences.objects.create(user=user, default_workspace=workspace)
    UserNotifications.objects.create(user=user)

    tokens = get_tokens_for_user(user)

    return Response({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'access': tokens['access'],
        'refresh': tokens['refresh'],
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    data = request.data
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return Response(
            {'error': 'email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    email_lower = email.lower().strip()
    user = authenticate(username=email_lower, password=password)
    if user is None:
        return Response(
            {'error': 'invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    tokens = get_tokens_for_user(user)
    return Response(tokens)


def _profile_to_response(user, request=None):
    avatar_url = ''
    if user.avatar:
        avatar_url = user.avatar.url
        if request:
            avatar_url = request.build_absolute_uri(avatar_url)
    return {
        'id': user.id,
        'email': user.email or '',
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'avatar': avatar_url or None,
        'phone': user.phone or '',
        'address': user.address or '',
    }


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    user = request.user
    if request.method == 'GET':
        return Response(_profile_to_response(user, request))

    # PATCH - update profile (avatar, phone, address are on User model)
    data = request.data
    avatar_file = request.FILES.get('avatar')
    avatar_removed = data.get('avatarRemoved') == 'true' or data.get('avatarRemoved') is True

    if 'first_name' in data:
        user.first_name = (data['first_name'] or '').strip()
    if 'last_name' in data:
        user.last_name = (data['last_name'] or '').strip()
    if 'phone' in data:
        user.phone = data['phone'] or ''
    if 'address' in data:
        user.address = data['address'] or ''
    if avatar_file:
        try:
            validate_image_file(avatar_file)
        except ValidationError as e:
            return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar = avatar_file
    elif avatar_removed and user.avatar:
        user.avatar.delete(save=False)
        user.avatar = None
    user.save()

    return Response(_profile_to_response(user, request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Change password for authenticated user."""
    data = request.data
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not old_password or not new_password or not confirm_password:
        return Response(
            {'error': 'old_password, new_password and confirm_password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if new_password != confirm_password:
        return Response(
            {'error': 'new password and confirm password do not match'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = request.user
    if not user.check_password(old_password):
        return Response(
            {'error': 'current password is incorrect'},
            status=status.HTTP_400_BAD_REQUEST
        )

    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    try:
        validate_password(new_password, user)
    except ValidationError as e:
        msg = list(e.messages)[0] if e.messages else 'Password does not meet requirements'
        return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    return Response({'success': True, 'message': 'Password has been changed'})


# --- Preferences and Notifications ---

def _get_or_create_preferences(user):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    return prefs


def _get_or_create_notifications(user):
    notifs, _ = UserNotifications.objects.get_or_create(user=user)
    return notifs


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def preferences_view(request):
    prefs = _get_or_create_preferences(request.user)
    if request.method == 'GET':
        return Response({
            'language': prefs.language,
            'timezone': prefs.timezone,
            'time_format': prefs.time_format,
            'first_day_of_week': prefs.first_day_of_week,
            'auto_sync': prefs.auto_sync,
            'default_workspace': prefs.default_workspace_id,
            'default_workspace_slug': prefs.default_workspace.slug if prefs.default_workspace else None,
            'default_workspace_name': prefs.default_workspace.name if prefs.default_workspace else None,
        })
    data = request.data
    for field in ('language', 'timezone', 'time_format', 'first_day_of_week', 'auto_sync'):
        if field in data:
            setattr(prefs, field, data[field] or '')
    if 'default_workspace' in data:
        ws_id = data['default_workspace']
        if ws_id is None or ws_id == '':
            prefs.default_workspace = None
        else:
            ws = Workspace.objects.filter(id=ws_id, owner=request.user).first()
            prefs.default_workspace = ws
    prefs.save()
    return Response({
        'language': prefs.language,
        'timezone': prefs.timezone,
        'time_format': prefs.time_format,
        'first_day_of_week': prefs.first_day_of_week,
        'auto_sync': prefs.auto_sync,
        'default_workspace': prefs.default_workspace_id,
        'default_workspace_slug': prefs.default_workspace.slug if prefs.default_workspace else None,
        'default_workspace_name': prefs.default_workspace.name if prefs.default_workspace else None,
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def notifications_view(request):
    notifs = _get_or_create_notifications(request.user)
    if request.method == 'GET':
        return Response({
            'new_project': notifs.new_project,
            'email': notifs.email,
            'projects_sync': notifs.projects_sync,
            'update': notifs.update,
            'in_app': notifs.in_app,
        })
    data = request.data
    for field in ('new_project', 'email', 'projects_sync', 'update', 'in_app'):
        if field in data:
            setattr(notifs, field, bool(data[field]))
    notifs.save()
    return Response({
        'new_project': notifs.new_project,
        'email': notifs.email,
        'projects_sync': notifs.projects_sync,
        'update': notifs.update,
        'in_app': notifs.in_app,
    })


# --- Password reset views (AllowAny) ---

def _generate_otp():
    return ''.join(random.choices(string.digits, k=6))


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request_view(request):
    data = request.data
    email = data.get('email')

    if not email:
        return Response(
            {'error': 'email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    email_lower = email.lower().strip()
    user = User.objects.filter(email=email_lower).first()
    if not user:
        return Response(
            {'error': 'no account found with this email'},
            status=status.HTTP_404_NOT_FOUND
        )

    otp = _generate_otp()
    PasswordResetOTP.objects.filter(email=email_lower).delete()
    PasswordResetOTP.objects.create(email=email_lower, otp=otp)

    subject = 'Pitchzo - Password Reset OTP'
    message = f'Your password reset OTP is: {otp}\n\nThis code expires in 15 minutes.'
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email_lower],
            fail_silently=False,
        )
    except Exception as e:
        return Response(
            {'error': 'failed to send email'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({'success': True, 'message': 'OTP sent to your email'})


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_verify_otp_view(request):
    data = request.data
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return Response(
            {'error': 'email and otp are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    email_lower = email.lower().strip()
    record = PasswordResetOTP.objects.filter(email=email_lower).first()
    if not record:
        return Response(
            {'error': 'invalid or expired OTP'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if record.is_expired():
        record.delete()
        return Response(
            {'error': 'OTP has expired'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if record.otp != otp.strip():
        return Response(
            {'error': 'invalid OTP'},
            status=status.HTTP_400_BAD_REQUEST
        )

    reset_token = str(uuid.uuid4())
    record.reset_token = reset_token
    record.save()

    return Response({'success': True, 'reset_token': reset_token})


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    data = request.data
    reset_token = data.get('reset_token')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not reset_token or not new_password or not confirm_password:
        return Response(
            {'error': 'reset_token, new_password and confirm_password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if new_password != confirm_password:
        return Response(
            {'error': 'passwords do not match'},
            status=status.HTTP_400_BAD_REQUEST
        )

    record = PasswordResetOTP.objects.filter(reset_token=reset_token).first()
    if not record:
        return Response(
            {'error': 'invalid or expired reset link'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if record.is_expired():
        record.delete()
        return Response(
            {'error': 'reset link has expired'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.filter(email=record.email).first()
    if not user:
        record.delete()
        return Response(
            {'error': 'user not found'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.set_password(new_password)
    user.save()
    record.delete()

    return Response({'success': True, 'message': 'Password has been reset'})


# --- Workspace views ---

def workspace_to_dict(ws):
    return {
        'id': ws.id,
        'name': ws.name,
        'slug': ws.slug,
        'type': ws.type or 'individual',
        'phone': ws.phone or '',
        'address': ws.address or '',
        'owner': ws.owner_id,
        'default_template_id': ws.default_template_id,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def workspace_list_create(request):
    if request.method == 'GET':
        fewfields = request.query_params.get('fewfields', '').lower() == 'true'
        if fewfields:
            data = list(
                Workspace.objects.filter(owner=request.user).values('name', 'slug')
            )
        else:
            workspaces = Workspace.objects.filter(owner=request.user)
            data = [workspace_to_dict(ws) for ws in workspaces]
        return Response(data)

    # POST
    data = request.data
    name = data.get('name')
    if not name:
        return Response(
            {'error': 'name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    slug = data.get('slug')
    ws_type = data.get('type', 'individual')
    if ws_type not in ('individual', 'company'):
        ws_type = 'individual'
    default_template_id = data.get('default_template_id')
    default_template = None
    if default_template_id:
        from proposalsapp.models import Template
        try:
            default_template = Template.objects.get(id=default_template_id)
        except (Template.DoesNotExist, ValueError):
            pass

    ws = Workspace.objects.create(
        name=name,
        slug=slug or '',
        type=ws_type,
        phone=data.get('phone', '') or '',
        address=data.get('address', '') or '',
        owner=request.user,
        default_template=default_template,
    )
    create_branding_for_workspace(ws, request.user)
    return Response(workspace_to_dict(ws), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def workspace_detail(request, workspace_id):
    workspace = get_object_or_404(
        Workspace, id=workspace_id, owner=request.user
    )

    if request.method == 'GET':
        return Response(workspace_to_dict(workspace))

    if request.method == 'DELETE':
        if Workspace.objects.filter(owner=request.user).count() <= 1:
            return Response(
                {'error': 'Cannot delete your only workspace'},
                status=status.HTTP_400_BAD_REQUEST
            )
        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PUT / PATCH
    data = request.data
    if 'name' in data:
        workspace.name = data['name']
    if 'slug' in data:
        workspace.slug = data['slug']
    if 'type' in data and data['type'] in ('individual', 'company'):
        workspace.type = data['type']
    if 'phone' in data:
        workspace.phone = data['phone'] or ''
    if 'address' in data:
        workspace.address = data['address'] or ''
    if 'default_template_id' in data:
        from proposalsapp.models import Template
        tid = data['default_template_id']
        if tid is None or tid == '':
            workspace.default_template = None
        else:
            try:
                workspace.default_template = Template.objects.get(id=tid)
            except (Template.DoesNotExist, ValueError):
                workspace.default_template = None
    workspace.save()
    return Response(workspace_to_dict(workspace))


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def workspace_by_slug(request, slug):
    """Get or update workspace by slug for the current user."""
    workspace = get_object_or_404(
        Workspace, slug=slug, owner=request.user
    )

    if request.method == 'GET':
        return Response(workspace_to_dict(workspace))

    # PATCH - allow updating default_template_id
    data = request.data
    if 'default_template_id' in data:
        from proposalsapp.models import Template
        tid = data['default_template_id']
        if tid is None or tid == '':
            workspace.default_template = None
        else:
            try:
                workspace.default_template = Template.objects.get(id=tid)
            except (Template.DoesNotExist, ValueError):
                workspace.default_template = None
        workspace.save()
    return Response(workspace_to_dict(workspace))


# --- Branding views (by slug) ---

@api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def branding_by_slug(request, slug):
    """Branding CRUD by workspace slug."""
    workspace = get_object_or_404(
        Workspace, slug=slug, owner=request.user
    )

    if request.method == 'GET':
        try:
            branding = workspace.branding
            return Response(branding_to_dict(branding, request))
        except Branding.DoesNotExist:
            return Response(
                {'error': 'branding not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    if request.method == 'POST':
        if hasattr(workspace, 'branding'):
            return Response(
                {'error': 'branding already exists for this workspace'},
                status=status.HTTP_400_BAD_REQUEST
            )
        branding = create_branding_for_workspace(workspace, request.user)
        data = request.data
        logo_file = request.FILES.get('logo')
        for field in ('primaryColor', 'secondaryColor', 'tertiaryColor',
                      'name', 'companyName', 'email', 'professionalTitle',
                      'address', 'phone'):
            if field in data:
                setattr(branding, field, data[field] or '')
        if logo_file:
            try:
                validate_image_file(logo_file)
            except ValidationError as e:
                return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)
            branding.logo = logo_file
        branding.save()
        return Response(branding_to_dict(branding, request), status=status.HTTP_201_CREATED)

    if request.method == 'DELETE':
        try:
            branding = workspace.branding
            branding.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Branding.DoesNotExist:
            return Response(
                {'error': 'branding not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    # PUT / PATCH
    try:
        branding = workspace.branding
    except Branding.DoesNotExist:
        return Response(
            {'error': 'branding not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    data = request.data
    logo_file = request.FILES.get('logo')
    logo_removed = data.get('logoRemoved') == 'true' or data.get('logoRemoved') is True

    for field in ('primaryColor', 'secondaryColor', 'tertiaryColor',
                  'name', 'companyName', 'email', 'professionalTitle',
                  'address', 'phone'):
        if field in data:
            setattr(branding, field, data[field] or '')

    if logo_file:
        try:
            validate_image_file(logo_file)
        except ValidationError as e:
            return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)
        if branding.logo:
            branding.logo.delete(save=False)
        branding.logo = logo_file
    elif logo_removed and branding.logo:
        branding.logo.delete(save=False)
        branding.logo = None

    branding.save()
    return Response(branding_to_dict(branding, request))


# --- Branding views (by id, legacy) ---

APP_PRIMARY_COLOR = '#975EED'
APP_SECONDARY_COLOR = '#86EFAC'
APP_TERTIARY_COLOR = '#93C5FD'


def branding_to_dict(b, request=None):
    logo_url = ''
    if b.logo:
        logo_url = b.logo.url
        if request:
            logo_url = request.build_absolute_uri(logo_url)
    return {
        'id': b.id,
        'workspace': b.workspace_id,
        'workspaceSlug': b.workspace.slug,
        'logo': logo_url,
        'primaryColor': b.primaryColor or APP_PRIMARY_COLOR,
        'secondaryColor': b.secondaryColor or APP_SECONDARY_COLOR,
        'tertiaryColor': b.tertiaryColor or APP_TERTIARY_COLOR,
        'name': b.name or '',
        'companyName': b.companyName or '',
        'email': b.email or '',
        'professionalTitle': b.professionalTitle or '',
        'address': b.address or '',
        'phone': b.phone or '',
    }


def create_branding_for_workspace(workspace, user):
    """Create branding with defaults: app primary color, user name, workspace name."""
    name = f"{user.first_name} {user.last_name}".strip() or user.email or ''
    return Branding.objects.create(
        workspace=workspace,
        primaryColor=APP_PRIMARY_COLOR,
        secondaryColor=APP_SECONDARY_COLOR,
        tertiaryColor=APP_TERTIARY_COLOR,
        name=name,
        companyName=workspace.name,
        email=user.email or '',
        professionalTitle='',
        address='',
        phone='',
    )


@api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def branding_detail(request, workspace_id):
    workspace = get_object_or_404(
        Workspace, id=workspace_id, owner=request.user
    )

    if request.method == 'GET':
        try:
            branding = workspace.branding
            return Response(branding_to_dict(branding, request))
        except Branding.DoesNotExist:
            return Response(
                {'error': 'branding not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    if request.method == 'POST':
        if hasattr(workspace, 'branding'):
            return Response(
                {'error': 'branding already exists for this workspace'},
                status=status.HTTP_400_BAD_REQUEST
            )
        branding = create_branding_for_workspace(workspace, request.user)
        data = request.data
        logo_file = request.FILES.get('logo')
        for field in ('primaryColor', 'secondaryColor', 'tertiaryColor',
                      'name', 'companyName', 'email', 'professionalTitle',
                      'address', 'phone'):
            if field in data:
                setattr(branding, field, data[field] or '')
        if logo_file:
            try:
                validate_image_file(logo_file)
            except ValidationError as e:
                return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)
            branding.logo = logo_file
        branding.save()
        return Response(branding_to_dict(branding, request), status=status.HTTP_201_CREATED)

    if request.method == 'DELETE':
        try:
            branding = workspace.branding
            branding.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Branding.DoesNotExist:
            return Response(
                {'error': 'branding not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    # PUT / PATCH
    try:
        branding = workspace.branding
    except Branding.DoesNotExist:
        return Response(
            {'error': 'branding not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    data = request.data
    logo_file = request.FILES.get('logo')
    logo_removed = data.get('logoRemoved') == 'true' or data.get('logoRemoved') is True
    for field in ('primaryColor', 'secondaryColor', 'tertiaryColor',
                  'name', 'companyName', 'email', 'professionalTitle',
                  'address', 'phone'):
        if field in data:
            setattr(branding, field, data[field] or '')
    if logo_file:
        try:
            validate_image_file(logo_file)
        except ValidationError as e:
            return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)
        if branding.logo:
            branding.logo.delete(save=False)
        branding.logo = logo_file
    elif logo_removed and branding.logo:
        branding.logo.delete(save=False)
        branding.logo = None
    branding.save()
    return Response(branding_to_dict(branding, request))
