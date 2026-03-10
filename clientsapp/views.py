from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authapp.models import User, Workspace
from .models import Client


def client_to_dict(client):
    return {
        'id': str(client.id),
        'name': client.name,
        'email': client.email,
        'type': client.type,
        'phone': client.phone or '',
        'address': client.address or '',
        'workspace_slug': client.workspace.slug,
        'user_id': str(client.created_by_id) if client.created_by_id else None,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def client_list_create(request, slug):
    """List or create clients for a workspace (by slug)."""
    workspace = get_object_or_404(
        Workspace, slug=slug, owner=request.user
    )

    if request.method == 'GET':
        clients = Client.objects.filter(workspace=workspace)
        return Response([client_to_dict(c) for c in clients])

    # POST
    data = request.data
    name = data.get('name')
    email = data.get('email')
    client_type = data.get('type', 'individual')

    if not name:
        return Response(
            {'error': 'name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not email:
        return Response(
            {'error': 'email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if client_type not in ('individual', 'company'):
        return Response(
            {'error': 'type must be "individual" or "company"'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if Client.objects.filter(workspace=workspace, email=email).exists():
        return Response(
            {'error': 'A client with this email already exists in this workspace'},
            status=status.HTTP_400_BAD_REQUEST
        )

    client = Client.objects.create(
        workspace=workspace,
        created_by=request.user,
        name=name,
        email=email,
        type=client_type,
        phone=data.get('phone', '') or '',
        address=data.get('address', '') or '',
    )
    return Response(client_to_dict(client), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def client_detail(request, slug, client_id):
    """Get, update, or delete a client (by workspace slug and client id)."""
    workspace = get_object_or_404(
        Workspace, slug=slug, owner=request.user
    )
    client = get_object_or_404(
        Client, id=client_id, workspace=workspace
    )

    if request.method == 'GET':
        return Response(client_to_dict(client))

    if request.method == 'DELETE':
        client.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PUT / PATCH
    data = request.data

    if 'name' in data:
        client.name = data['name']
    if 'email' in data:
        new_email = data['email']
        if Client.objects.filter(workspace=workspace, email=new_email).exclude(id=client.id).exists():
            return Response(
                {'error': 'A client with this email already exists in this workspace'},
                status=status.HTTP_400_BAD_REQUEST
            )
        client.email = new_email
    if 'type' in data and data['type'] in ('individual', 'company'):
        client.type = data['type']
    if 'phone' in data:
        client.phone = data['phone'] or ''
    if 'address' in data:
        client.address = data['address'] or ''
    if 'user_id' in data:
        if data['user_id'] is None or data['user_id'] == '':
            client.created_by = None
        else:
            try:
                user = User.objects.get(id=data['user_id'])
                client.created_by = user
            except (User.DoesNotExist, ValueError):
                client.created_by = None

    client.save()
    return Response(client_to_dict(client))
