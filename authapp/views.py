import random
import string
import uuid
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Workspace, Branding, PasswordResetOTP


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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    user = request.user
    return Response({
        'id': user.id,
        'email': user.email or '',
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
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
        'owner': ws.owner_id
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def workspace_list_create(request):
    if request.method == 'GET':
        workspaces = Workspace.objects.filter(owner=request.user)
        return Response([workspace_to_dict(ws) for ws in workspaces])

    # POST
    data = request.data
    name = data.get('name')
    if not name:
        return Response(
            {'error': 'name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    slug = data.get('slug')
    ws = Workspace.objects.create(
        name=name,
        slug=slug or '',
        owner=request.user
    )
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
        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PUT / PATCH
    data = request.data
    if 'name' in data:
        workspace.name = data['name']
    if 'slug' in data:
        workspace.slug = data['slug']
    workspace.save()
    return Response(workspace_to_dict(workspace))


# --- Branding views ---

def branding_to_dict(b):
    return {
        'id': b.id,
        'workspace': b.workspace_id,
        'logo': b.logo,
        'primaryColor': b.primaryColor,
        'secondaryColor': b.secondaryColor
    }


@api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def branding_detail(request, workspace_id):
    workspace = get_object_or_404(
        Workspace, id=workspace_id, owner=request.user
    )

    if request.method == 'GET':
        try:
            branding = workspace.branding
            return Response(branding_to_dict(branding))
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
        data = request.data
        branding = Branding.objects.create(
            workspace=workspace,
            logo=data.get('logo', ''),
            primaryColor=data.get('primaryColor', ''),
            secondaryColor=data.get('secondaryColor', '')
        )
        return Response(branding_to_dict(branding), status=status.HTTP_201_CREATED)

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
    if 'logo' in data:
        branding.logo = data['logo']
    if 'primaryColor' in data:
        branding.primaryColor = data['primaryColor']
    if 'secondaryColor' in data:
        branding.secondaryColor = data['secondaryColor']
    branding.save()
    return Response(branding_to_dict(branding))
