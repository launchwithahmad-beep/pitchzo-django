from rest_framework import permissions


def is_workspace_owner(request, workspace):
    """Check if the authenticated user owns the workspace."""
    return request.user.is_authenticated and workspace.owner == request.user


def is_branding_owner(request, branding):
    """Check if the authenticated user owns the workspace that the branding belongs to."""
    return (
        request.user.is_authenticated
        and branding.workspace.owner == request.user
    )
