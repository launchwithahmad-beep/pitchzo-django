import json
from decimal import Decimal

from django.db.models import Q
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from pitchzo.validators import validate_image_file, validation_error_message
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authapp.models import User, Workspace
from clientsapp.models import Client

from .models import Portfolio, PortfolioImage, PortfolioSource, PortfolioType, Proposal, ProposalCategory, ProposalGenBy, ProposalSentVia, ProposalStatus, Template, TemplateCategory


def portfolio_to_dict(portfolio, request=None):
    image_url = ''
    if portfolio.image:
        image_url = portfolio.image.url
        if request:
            image_url = request.build_absolute_uri(image_url)
    extra_images = []
    for pi in portfolio.extra_images.all().order_by('order'):
        url = pi.image.url if pi.image else ''
        if request and url:
            url = request.build_absolute_uri(url)
        extra_images.append({'id': pi.id, 'image': url, 'order': pi.order})
    return {
        'id': str(portfolio.id),
        'title': portfolio.title,
        'type': portfolio.type,
        'detail': portfolio.detail or '',
        'description': portfolio.description or '',
        'tags': portfolio.tags or [],
        'source': portfolio.source,
        'resource': portfolio.resource or '',
        'resource_link': portfolio.resource_link or '',
        'fetch_date': portfolio.fetch_date.isoformat(),
        'last_rsync': portfolio.last_rsync.isoformat() if portfolio.last_rsync else None,
        'workspace_id': portfolio.workspace_id,
        'workspace_slug': portfolio.workspace.slug,
        'user_id': str(portfolio.user_id) if portfolio.user_id else None,
        'image': image_url,
        'extra_images': extra_images,
        'created_at': portfolio.created_at.isoformat(),
        'updated_at': portfolio.updated_at.isoformat(),
    }


def template_to_dict(template, request=None):
    image_url = ''
    if template.image:
        image_url = template.image.url
        if request:
            image_url = request.build_absolute_uri(image_url)
    return {
        'id': template.id,
        'title': template.title,
        'description': template.description or '',
        'image': image_url,
        'category': template.category,
        'content': template.content,
        'active': template.active,
    }


def proposal_to_dict(proposal, request=None):
    data = {
        'id': str(proposal.id),
        'title': proposal.title,
        'description': proposal.description or '',
        'status': proposal.status,
        'sentvia': proposal.sentvia,
        'genby': proposal.genby,
        'company_name': proposal.company_name or '',
        'category': proposal.category,
        'client_id': str(proposal.client_id) if proposal.client_id else None,
        'client_name': proposal.client.name if proposal.client else None,
        'sender_id': str(proposal.sender_id) if proposal.sender_id else None,
        'workspace_id': proposal.workspace_id,
        'workspace_slug': proposal.workspace.slug,
        'project_ids': [str(p.id) for p in proposal.projects.all()],
        'currency': proposal.currency,
        'subtotal': str(proposal.subtotal),
        'tax': str(proposal.tax),
        'discount': str(proposal.discount) if proposal.discount is not None else None,
        'total': str(proposal.total),
        'created_at': proposal.created_at.isoformat(),
        'updated_at': proposal.updated_at.isoformat(),
    }
    return data


# --- Template CRUD (authenticated, no workspace) ---

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def template_list_create(request):
    """List all templates or create a new one."""
    if request.method == 'GET':
        templates_qs = Template.objects.filter(active=True).order_by('id')
        category_filter = request.query_params.get('category', '').strip()
        if category_filter and category_filter in [c[0] for c in TemplateCategory.choices]:
            templates_qs = templates_qs.filter(category=category_filter)
        search_q = request.query_params.get('search', '').strip()
        if search_q:
            templates_qs = templates_qs.filter(
                Q(title__icontains=search_q) | Q(description__icontains=search_q)
            )
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 12))
        page_size = min(max(page_size, 1), 100)
        total_count = templates_qs.count()
        total_pages = (total_count + page_size - 1) // page_size if page_size else 1
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size
        templates = list(templates_qs[offset:offset + page_size])
        return Response({
            'results': [template_to_dict(t, request) for t in templates],
            'count': total_count,
            'total_pages': total_pages,
            'page': page,
            'page_size': page_size,
        })

    # POST
    data = request.data
    image_file = request.FILES.get('image')

    title = data.get('title')
    category = data.get('category')
    content = data.get('content')

    if not title:
        return Response(
            {'error': 'title is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not category:
        return Response(
            {'error': 'category is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    valid_categories = [c[0] for c in TemplateCategory.choices]
    if category not in valid_categories:
        return Response(
            {'error': f'category must be one of: {", ".join(valid_categories)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not content:
        return Response(
            {'error': 'content is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not image_file:
        return Response(
            {'error': 'image is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        validate_image_file(image_file)
    except ValidationError as e:
        return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)

    template = Template.objects.create(
        title=title,
        description=data.get('description') or None,
        image=image_file,
        category=category,
        content=content,
        active=data.get('active', True) if isinstance(data.get('active'), bool) else True,
    )
    return Response(template_to_dict(template, request), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def template_detail(request, template_id):
    """Get, update, or delete a template."""
    template = get_object_or_404(Template, id=template_id)

    if request.method == 'GET':
        return Response(template_to_dict(template, request))

    if request.method == 'DELETE':
        if template.image:
            template.image.delete(save=False)
        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PUT / PATCH
    data = request.data
    image_file = request.FILES.get('image')

    if 'title' in data:
        template.title = data['title']
    if 'description' in data:
        template.description = data['description'] or None
    if 'category' in data:
        valid_categories = [c[0] for c in TemplateCategory.choices]
        if data['category'] in valid_categories:
            template.category = data['category']
    if 'content' in data:
        template.content = data['content']
    if 'active' in data:
        template.active = bool(data['active'])
    if image_file:
        try:
            validate_image_file(image_file)
        except ValidationError as e:
            return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)
        if template.image:
            template.image.delete(save=False)
        template.image = image_file

    template.save()
    return Response(template_to_dict(template, request))


# --- Portfolio CRUD (authenticated, workspace-scoped) ---

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def portfolio_list_create(request, slug):
    """List or create portfolios for a workspace (by slug)."""
    workspace = get_object_or_404(
        Workspace, slug=slug, owner=request.user
    )

    if request.method == 'GET':
        portfolios_qs = Portfolio.objects.filter(workspace=workspace).order_by('-created_at')
        type_filter = request.query_params.get('type', '').strip()
        if type_filter and type_filter in [t[0] for t in PortfolioType.choices]:
            portfolios_qs = portfolios_qs.filter(type=type_filter)
        search_q = request.query_params.get('search', '').strip()
        if search_q:
            portfolios_qs = portfolios_qs.filter(
                Q(title__icontains=search_q) | Q(description__icontains=search_q)
            )
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 12))
        page_size = min(max(page_size, 1), 100)
        total_count = portfolios_qs.count()
        total_pages = (total_count + page_size - 1) // page_size if page_size else 1
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size
        portfolios = list(portfolios_qs[offset:offset + page_size])
        return Response({
            'results': [portfolio_to_dict(p, request) for p in portfolios],
            'count': total_count,
            'total_pages': total_pages,
            'page': page,
            'page_size': page_size,
        })

    # POST
    data = request.data
    image_file = request.FILES.get('image')

    title = data.get('title')
    if not title:
        return Response(
            {'error': 'title is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not image_file:
        return Response(
            {'error': 'image is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        validate_image_file(image_file)
    except ValidationError as e:
        return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)

    source = data.get('source', 'uploaded')
    if source not in [s[0] for s in PortfolioSource.choices]:
        source = 'uploaded'

    portfolio_type = data.get('type', 'others')
    if portfolio_type not in [t[0] for t in PortfolioType.choices]:
        portfolio_type = 'others'

    tags = data.get('tags')
    if isinstance(tags, list):
        pass
    elif isinstance(tags, str):
        try:
            parsed = json.loads(tags)
            tags = parsed if isinstance(parsed, list) else [t.strip() for t in tags.split(',') if t.strip()]
        except (json.JSONDecodeError, TypeError):
            tags = [t.strip() for t in tags.split(',') if t.strip()]
    else:
        tags = []

    portfolio = Portfolio.objects.create(
        title=title,
        type=portfolio_type,
        detail=data.get('detail') or None,
        description=data.get('description') or None,
        tags=tags,
        source=source,
        resource=data.get('resource') or None,
        resource_link=data.get('resource_link') or None,
        workspace=workspace,
        user=request.user,
        image=image_file,
    )

    # Handle extra images (max 10)
    extra_files = request.FILES.getlist('extra_images')[:10]
    for i, ef in enumerate(extra_files):
        try:
            validate_image_file(ef)
            PortfolioImage.objects.create(portfolio=portfolio, image=ef, order=i)
        except ValidationError:
            pass

    return Response(portfolio_to_dict(portfolio, request), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def portfolio_detail(request, slug, portfolio_id):
    """Get, update, or delete a portfolio (by workspace slug and portfolio id)."""
    workspace = get_object_or_404(
        Workspace, slug=slug, owner=request.user
    )
    portfolio = get_object_or_404(
        Portfolio, id=portfolio_id, workspace=workspace
    )

    if request.method == 'GET':
        return Response(portfolio_to_dict(portfolio, request))

    if request.method == 'DELETE':
        if portfolio.image:
            portfolio.image.delete(save=False)
        for pi in portfolio.extra_images.all():
            if pi.image:
                pi.image.delete(save=False)
        portfolio.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PUT / PATCH
    data = request.data
    image_file = request.FILES.get('image')

    if 'title' in data:
        portfolio.title = data['title']
    if 'type' in data and data['type'] in [t[0] for t in PortfolioType.choices]:
        portfolio.type = data['type']
    if 'detail' in data:
        portfolio.detail = data['detail'] or None
    if 'description' in data:
        portfolio.description = data['description'] or None
    if 'tags' in data:
        tags = data['tags']
        if isinstance(tags, list):
            portfolio.tags = tags
        elif isinstance(tags, str):
            portfolio.tags = [t.strip() for t in tags.split(',') if t.strip()]
    if 'source' in data and data['source'] in [s[0] for s in PortfolioSource.choices]:
        portfolio.source = data['source']
    if 'resource' in data:
        portfolio.resource = data['resource'] or None
    if 'resource_link' in data:
        portfolio.resource_link = data['resource_link'] or None

    if image_file:
        try:
            validate_image_file(image_file)
        except ValidationError as e:
            return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)
        if portfolio.image:
            portfolio.image.delete(save=False)
        portfolio.image = image_file

    # Delete extra images by IDs (do this first so we know correct count for adding)
    delete_ids = data.get('delete_extra_image_ids')
    if delete_ids is not None:
        if isinstance(delete_ids, str):
            try:
                delete_ids = json.loads(delete_ids)
            except (json.JSONDecodeError, TypeError):
                delete_ids = []
        if isinstance(delete_ids, list):
            for pid in delete_ids:
                try:
                    pi = portfolio.extra_images.get(id=pid)
                    if pi.image:
                        pi.image.delete(save=False)
                    pi.delete()
                except (PortfolioImage.DoesNotExist, TypeError, ValueError):
                    pass

    # Add new extra images (max 10 total)
    extra_files = request.FILES.getlist('extra_images')
    current_count = portfolio.extra_images.count()
    for i, ef in enumerate(extra_files[: max(0, 10 - current_count)]):
        try:
            validate_image_file(ef)
            PortfolioImage.objects.create(portfolio=portfolio, image=ef, order=current_count + i)
        except ValidationError:
            pass

    portfolio.save()
    return Response(portfolio_to_dict(portfolio, request))


# --- Proposal CRUD (authenticated, workspace-scoped) ---

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def proposal_list_create(request, slug):
    """List or create proposals for a workspace (by slug)."""
    workspace = get_object_or_404(
        Workspace, slug=slug, owner=request.user
    )

    if request.method == 'GET':
        proposals = Proposal.objects.filter(workspace=workspace)
        return Response([proposal_to_dict(p, request) for p in proposals])

    # POST
    data = request.data

    title = data.get('title')
    currency = data.get('currency')
    subtotal = data.get('subtotal')
    tax = data.get('tax')
    total = data.get('total')

    if not title:
        return Response(
            {'error': 'title is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not currency:
        return Response(
            {'error': 'currency is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if subtotal is None or subtotal == '':
        return Response(
            {'error': 'subtotal is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if tax is None or tax == '':
        return Response(
            {'error': 'tax is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if total is None or total == '':
        return Response(
            {'error': 'total is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    sentvia = data.get('sentvia')
    if not sentvia:
        return Response(
            {'error': 'sentvia is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    valid_sentvia = [s[0] for s in ProposalSentVia.choices]
    if sentvia not in valid_sentvia:
        return Response(
            {'error': f'sentvia must be one of: {", ".join(valid_sentvia)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    category = data.get('category')
    if not category:
        return Response(
            {'error': 'category is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    valid_categories = [c[0] for c in ProposalCategory.choices]
    if category not in valid_categories:
        return Response(
            {'error': f'category must be one of: {", ".join(valid_categories)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        subtotal_val = Decimal(str(subtotal))
        tax_val = Decimal(str(tax))
        total_val = Decimal(str(total))
    except (ValueError, TypeError):
        return Response(
            {'error': 'subtotal, tax, and total must be valid numbers'},
            status=status.HTTP_400_BAD_REQUEST
        )

    discount_val = None
    if data.get('discount') is not None and data.get('discount') != '':
        try:
            discount_val = Decimal(str(data['discount']))
        except (ValueError, TypeError):
            pass

    client = None
    client_id = data.get('client_id')
    if client_id:
        client = Client.objects.filter(
            id=client_id, workspace=workspace
        ).first()
        if not client:
            return Response(
                {'error': 'client not found or does not belong to this workspace'},
                status=status.HTTP_400_BAD_REQUEST
            )

    status_val = data.get('status', 'draft')
    if status_val not in [s[0] for s in ProposalStatus.choices]:
        status_val = 'draft'

    genby_val = data.get('genby', 'manual')
    if genby_val not in [g[0] for g in ProposalGenBy.choices]:
        genby_val = 'manual'

    proposal = Proposal.objects.create(
        title=title,
        description=data.get('description') or None,
        status=status_val,
        sentvia=sentvia,
        genby=genby_val,
        company_name=data.get('company_name') or '',
        category=category,
        client=client,
        sender=request.user,
        workspace=workspace,
        currency=currency,
        subtotal=subtotal_val,
        tax=tax_val,
        discount=discount_val,
        total=total_val,
    )
    project_ids = data.get('project_ids') or []
    if project_ids:
        portfolios = Portfolio.objects.filter(id__in=project_ids, workspace=workspace)
        proposal.projects.set(portfolios)
    return Response(proposal_to_dict(proposal, request), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def proposal_detail(request, slug, proposal_id):
    """Get, update, or delete a proposal (by workspace slug and proposal id)."""
    workspace = get_object_or_404(
        Workspace, slug=slug, owner=request.user
    )
    proposal = get_object_or_404(
        Proposal, id=proposal_id, workspace=workspace
    )

    if request.method == 'GET':
        return Response(proposal_to_dict(proposal, request))

    if request.method == 'DELETE':
        proposal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PUT / PATCH
    data = request.data

    if 'title' in data:
        proposal.title = data['title']
    if 'description' in data:
        proposal.description = data['description'] or None
    if 'status' in data and data['status'] in [s[0] for s in ProposalStatus.choices]:
        proposal.status = data['status']
    if 'sentvia' in data and data['sentvia'] in [s[0] for s in ProposalSentVia.choices]:
        proposal.sentvia = data['sentvia']
    if 'genby' in data and data['genby'] in [g[0] for g in ProposalGenBy.choices]:
        proposal.genby = data['genby']
    if 'company_name' in data:
        proposal.company_name = data['company_name'] or ''
    if 'category' in data and data['category'] in [c[0] for c in ProposalCategory.choices]:
        proposal.category = data['category']
    if 'currency' in data:
        proposal.currency = data['currency']
    if 'subtotal' in data:
        try:
            proposal.subtotal = Decimal(str(data['subtotal']))
        except (ValueError, TypeError):
            pass
    if 'tax' in data:
        try:
            proposal.tax = Decimal(str(data['tax']))
        except (ValueError, TypeError):
            pass
    if 'discount' in data:
        if data['discount'] is None or data['discount'] == '':
            proposal.discount = None
        else:
            try:
                proposal.discount = Decimal(str(data['discount']))
            except (ValueError, TypeError):
                pass
    if 'total' in data:
        try:
            proposal.total = Decimal(str(data['total']))
        except (ValueError, TypeError):
            pass

    if 'client_id' in data:
        if data['client_id'] is None or data['client_id'] == '':
            proposal.client = None
        else:
            client = Client.objects.filter(
                id=data['client_id'], workspace=workspace
            ).first()
            proposal.client = client

    if 'sender_id' in data:
        if data['sender_id'] is None or data['sender_id'] == '':
            proposal.sender = None
        else:
            try:
                sender = User.objects.get(id=data['sender_id'])
                proposal.sender = sender
            except (User.DoesNotExist, ValueError):
                proposal.sender = None

    if 'project_ids' in data:
        project_ids = data['project_ids'] or []
        portfolios = Portfolio.objects.filter(id__in=project_ids, workspace=workspace)
        proposal.projects.set(portfolios)

    proposal.save()
    return Response(proposal_to_dict(proposal, request))
