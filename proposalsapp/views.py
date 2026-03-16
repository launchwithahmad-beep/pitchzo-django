import json
import os
import uuid
from decimal import Decimal

from django.core.files.storage import default_storage
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.template import Template as DjangoTemplate, Context
from django.utils.html import escape
import re
from pitchzo.validators import validate_image_file, validation_error_message
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authapp.models import User, Workspace
from clientsapp.models import Client

from .models import (
    Portfolio,
    PortfolioImage,
    PortfolioSource,
    PortfolioType,
    Proposal,
    ProposalCategory,
    ProposalGenBy,
    ProposalSection,
    ProposalSectionType,
    ProposalSentVia,
    ProposalStatus,
    Template,
    TemplateCategory,
    TemplateSection,
)

VALID_SECTION_TYPES = [c[0] for c in ProposalSectionType.choices]


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


def template_section_to_dict(ts):
    return {
        'section_type': ts.section_type,
        'title': ts.title,
        'content': ts.content or '',
        'order': ts.order,
    }


def template_to_dict(template, request=None):
    image_url = ''
    if template.image:
        image_url = template.image.url
        if request:
            image_url = request.build_absolute_uri(image_url)
    sections = [
        template_section_to_dict(ts)
        for ts in template.template_sections.all().order_by('order', 'section_type')
    ]
    return {
        'id': template.id,
        'title': template.title,
        'description': template.description or '',
        'image': image_url,
        'category': template.category,
        'active': template.active,
        'sections': sections,
    }


def section_to_dict(section, request=None):
    return {
        'id': str(section.id),
        'section_type': section.section_type,
        'title': section.title,
        'content': section.content or {},
        'order': section.order,
        'created_at': section.created_at.isoformat(),
        'updated_at': section.updated_at.isoformat(),
    }


def proposal_to_dict(proposal, request=None):
    template = proposal.template
    template_image = ''
    if template and template.image:
        template_image = template.image.url
        if request:
            template_image = request.build_absolute_uri(template_image)

    sections = [
        section_to_dict(s, request)
        for s in proposal.sections.all().order_by('order', 'created_at')
    ]

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
        'template_id': template.id if template else None,
        'template_title': template.title if template else None,
        'template_image': template_image,
        'template_category': template.category if template else None,
        'project_ids': [str(p.id) for p in proposal.projects.all()],
        'projects': [portfolio_to_dict(p, request) for p in proposal.projects.all()],
        'sections': sections,
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
    sections_data = data.get('sections')

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
    if not image_file:
        return Response(
            {'error': 'image is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        validate_image_file(image_file)
    except ValidationError as e:
        return Response({'error': validation_error_message(e)}, status=status.HTTP_400_BAD_REQUEST)

    if sections_data is not None:
        if not isinstance(sections_data, list):
            return Response(
                {'error': 'sections must be a list of { section_type, title, content }'},
                status=status.HTTP_400_BAD_REQUEST
            )
        seen_types = set()
        for i, item in enumerate(sections_data):
            if not isinstance(item, dict):
                return Response(
                    {'error': f'sections[{i}] must be an object with section_type, title, content'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            st = item.get('section_type')
            if not st:
                return Response(
                    {'error': f'sections[{i}] section_type is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if st not in VALID_SECTION_TYPES:
                return Response(
                    {'error': f'sections[{i}] section_type must be one of: {", ".join(VALID_SECTION_TYPES)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if st in seen_types:
                return Response(
                    {'error': f'sections: section_type "{st}" cannot be repeated'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            seen_types.add(st)

    template = Template.objects.create(
        title=title,
        description=data.get('description') or None,
        image=image_file,
        category=category,
        content=content or '',
        active=data.get('active', True) if isinstance(data.get('active'), bool) else True,
    )
    if sections_data:
        section_type_labels = dict(ProposalSectionType.choices)
        for order, item in enumerate(sections_data):
            st = item.get('section_type')
            TemplateSection.objects.create(
                template=template,
                section_type=st,
                title=item.get('title') or section_type_labels.get(st, st.replace('_', ' ').title()),
                content=item.get('content') or '',
                order=order,
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
    if 'active' in data:
        template.active = bool(data['active'])
    if 'sections' in data:
        sections_data = data['sections']
        if not isinstance(sections_data, list):
            return Response(
                {'error': 'sections must be a list of { section_type, title, content }'},
                status=status.HTTP_400_BAD_REQUEST
            )
        seen_types = set()
        for i, item in enumerate(sections_data):
            if not isinstance(item, dict):
                return Response(
                    {'error': f'sections[{i}] must be an object with section_type, title, content'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            st = item.get('section_type')
            if not st:
                return Response(
                    {'error': f'sections[{i}] section_type is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if st not in VALID_SECTION_TYPES:
                return Response(
                    {'error': f'sections[{i}] section_type must be one of: {", ".join(VALID_SECTION_TYPES)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if st in seen_types:
                return Response(
                    {'error': f'sections: section_type "{st}" cannot be repeated'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            seen_types.add(st)
        template.template_sections.all().delete()
        section_type_labels = dict(ProposalSectionType.choices)
        for order, item in enumerate(sections_data):
            st = item.get('section_type')
            TemplateSection.objects.create(
                template=template,
                section_type=st,
                title=item.get('title') or section_type_labels.get(st, st.replace('_', ' ').title()),
                content=item.get('content') or '',
                order=order,
            )
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
            portfolio.tags = [str(t).strip() for t in tags if t]
        elif isinstance(tags, str):
            try:
                parsed = json.loads(tags)
                portfolio.tags = [str(t).strip() for t in parsed if t] if isinstance(parsed, list) else [t.strip() for t in tags.split(',') if t.strip()]
            except (json.JSONDecodeError, TypeError):
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


# --- Overview Stats (authenticated, workspace-scoped) ---

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def workspace_overview(request, slug):
    """Return overview stats for a workspace: proposal counts, portfolio count, etc."""
    workspace = get_object_or_404(Workspace, slug=slug, owner=request.user)

    total_proposals = Proposal.objects.filter(workspace=workspace).count()
    sent_proposals = Proposal.objects.filter(
        workspace=workspace, status=ProposalStatus.SENT
    ).count()
    drafts = Proposal.objects.filter(
        workspace=workspace, status=ProposalStatus.DRAFT
    ).count()
    portfolio_assets = Portfolio.objects.filter(workspace=workspace).count()

    today = timezone.now().date()
    drafts_updated_today = Proposal.objects.filter(
        workspace=workspace,
        status=ProposalStatus.DRAFT,
        updated_at__date=today,
    ).count()

    week_ago = today - timezone.timedelta(days=7)
    proposals_this_week = Proposal.objects.filter(
        workspace=workspace,
        created_at__date__gte=week_ago,
    ).count()

    proposals_using_portfolio = Proposal.objects.filter(
        workspace=workspace
    ).annotate(projects_count=Count('projects')).filter(
        projects_count__gt=0
    ).count()

    sent_percentage = (
        round(sent_proposals / total_proposals * 100)
        if total_proposals > 0
        else 0
    )

    return Response({
        'total_proposals': total_proposals,
        'sent_proposals': sent_proposals,
        'drafts': drafts,
        'portfolio_assets': portfolio_assets,
        'drafts_updated_today': drafts_updated_today,
        'proposals_this_week': proposals_this_week,
        'proposals_using_portfolio': proposals_using_portfolio,
        'sent_percentage': sent_percentage,
    })


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

    template = None
    template_id = data.get('template_id')
    if template_id is not None and template_id != '':
        template = Template.objects.filter(id=template_id).first()
        if not template:
            return Response(
                {'error': 'template not found'},
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
        template=template,
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

    # Add default cover page section (non-deletable)
    ProposalSection.objects.create(
        proposal=proposal,
        section_type=ProposalSectionType.COVER_PAGE,
        title=dict(ProposalSectionType.choices).get(ProposalSectionType.COVER_PAGE, 'Cover Page'),
        content={},
        order=0,
    )

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

    if 'template_id' in data:
        if data['template_id'] is None or data['template_id'] == '':
            proposal.template = None
        else:
            template = Template.objects.filter(id=data['template_id']).first()
            proposal.template = template

    proposal.save()
    return Response(proposal_to_dict(proposal, request))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def proposal_preview(request, slug, proposal_id):
    """Render proposal preview: template sections filled with builder data. Returns rendered HTML per section."""
    workspace = get_object_or_404(Workspace, slug=slug, owner=request.user)
    proposal = get_object_or_404(Proposal, id=proposal_id, workspace=workspace)

    if not proposal.template_id:
        return Response(
            {'error': 'Proposal has no template selected'},
            status=status.HTTP_400_BAD_REQUEST
        )

    template = proposal.template

    # Build lookup: proposal section by section_type (for builder data)
    proposal_sections_by_type = {
        s.section_type: s
        for s in proposal.sections.all().order_by('order', 'created_at')
    }

    # Build projects list for template context (image_url, title, description, detail)
    projects = []
    for p in proposal.projects.all():
        image_url = ''
        if p.image:
            image_url = request.build_absolute_uri(p.image.url) if request else p.image.url
        projects.append({
            'image_url': image_url,
            'title': p.title or '',
            'description': p.description or '',
            'detail': p.detail or '',
        })

    def _user_display_name(user):
        parts = [user.first_name, user.last_name] if user else []
        return ' '.join(p for p in parts if p) or (getattr(user, 'email', None) or 'User')

    prepared_by = _user_display_name(proposal.sender) if proposal.sender else _user_display_name(request.user)

    date_str = proposal.updated_at.strftime('%b %d, %Y') if proposal.updated_at else ''
    client_name = proposal.client.name if proposal.client else ''

    def _build_section_context(section, section_type, request):
        """Build template context from section.content for section-specific variables."""
        c = (section.content or {}) if section else {}
        req = request

        def _abs_url(url):
            if url and req:
                return req.build_absolute_uri(url)
            return url or ''

        out = {}
        if section_type == 'services':
            items = c.get('items') or []
            out['services'] = [{
                'title': i.get('title'),
                'duration': i.get('duration'),
                'price': i.get('price'),
                'description': i.get('description'),
            } for i in items]

        elif section_type == 'pricing_estimate_tiers':
            tiers = c.get('tiers') or []
            out['tiers'] = [{
                'title': t.get('title'),
                'description': t.get('description'),
                'price': t.get('price'),
                'currency': t.get('currency'),
            } for t in tiers]
            out['currency'] = proposal.currency if proposal else ''

        elif section_type == 'testimonials_reviews':
            items = c.get('items') or []
            out['testimonials'] = [{
                'image_url': _abs_url(i.get('image')),
                'quote': i.get('comment') or i.get('quote'),
                'name': i.get('name') or i.get('reviewerName'),
                'role': i.get('designation'),
                'company': i.get('company'),
            } for i in items]

        elif section_type == 'meet_the_team':
            members = c.get('members') or []
            out['members'] = [{
                'image_url': _abs_url(m.get('image')),
                'name': m.get('name'),
                'role': m.get('designation'),
                'bio': m.get('description'),
            } for m in members]

        elif section_type == 'timeline_sprints':
            items = c.get('items') or []
            out['phases'] = [{
                'title': i.get('title') or i.get('smallTitle'),
                'duration': i.get('estimateTime'),
            } for i in items]
            out['milestones'] = c.get('milestones') or ''

        elif section_type == 'faqs':
            items = c.get('items') or []
            out['faqs'] = [{'question': i.get('question'), 'answer': i.get('answer')} for i in items]

        elif section_type == 'next_steps_cta':
            out['headline'] = c.get('headline') or 'Next Steps'
            out['next_steps'] = c.get('next_steps') or []
            out['contact'] = c.get('contact') or ''
            if c.get('ctaText'):
                out['next_steps'] = [c['ctaText']] if not out['next_steps'] else out['next_steps']

        elif section_type == 'acceptance_esignature':
            out['acceptance_statement'] = c.get('acceptance_statement') or 'By signing below, you accept the terms of this proposal.'
            out['signer_name'] = c.get('signer_name') or prepared_by
            out['signer_title'] = c.get('signer_title')
            out['signer_email'] = c.get('signer_email')
            out['signature_date'] = date_str
            sig_img = c.get('signatureImage') or c.get('signature_image_url')
            out['signature_image_url'] = _abs_url(sig_img) if isinstance(sig_img, str) else ''
            out['signature_text'] = c.get('signature_text')

        elif section_type == 'payment_schedule':
            out['milestones'] = c.get('milestones') or c.get('items') or []
            out['payment_methods'] = c.get('payment_methods') or ''

        return out

    # Iterate over TEMPLATE sections (in template order) - show all that have content
    sections_html = []
    for ts in template.template_sections.all().order_by('order', 'section_type'):
        content_stripped = (ts.content or '').strip()
        if not content_stripped:
            continue

        # Get builder data from proposal section if it exists
        section = proposal_sections_by_type.get(ts.section_type)
        content_html = ((section.content or {}).get('html') or '') if section else ''
        title = section.title if section else ts.title

        ctx = {
            'title': title,
            'content': mark_safe(content_html),
            'project_title': proposal.title,
            'client_name': client_name,
            'prepared_by': prepared_by,
            'date': date_str,
            'tagline': '',
            'projects': projects,
        }
        ctx.update(_build_section_context(section, ts.section_type, request))

        try:
            t = DjangoTemplate(ts.content)
            rendered = t.render(Context(ctx))
            # If template rendered a full HTML document, extract style + body for embedding
            parts = []
            style_match = re.search(r'<style[^>]*>(.*?)</style>', rendered, re.DOTALL | re.IGNORECASE)
            if style_match:
                parts.append(f'<style>{style_match.group(1)}</style>')
            body_match = re.search(r'<body[^>]*>(.*?)</body>', rendered, re.DOTALL | re.IGNORECASE)
            if body_match:
                body_html = body_match.group(1).strip()
            else:
                body_html = rendered

            # For PDF preview: remove onclick handlers (openProjectModal etc.) - scripts don't run in embedded HTML
            body_html = re.sub(r'\s+onclick="[^"]*"', '', body_html)
            # Remove script blocks (they don't execute in React dangerouslySetInnerHTML)
            body_html = re.sub(r'<script[^>]*>.*?</script>', '', body_html, flags=re.DOTALL | re.IGNORECASE)

            parts.append(body_html)
            sections_html.append({'html': ''.join(parts)})
        except Exception:
            continue

    return Response({
        'sections': sections_html,
        'proposal_title': proposal.title,
        'template_title': template.title if template else None,
        'prepared_by': prepared_by,
        'date': date_str,
    })


# --- Proposal Sections API ---

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def proposal_section_list_create(request, slug, proposal_id):
    """List or create sections for a proposal."""
    workspace = get_object_or_404(Workspace, slug=slug, owner=request.user)
    proposal = get_object_or_404(Proposal, id=proposal_id, workspace=workspace)

    if request.method == 'GET':
        sections = proposal.sections.all().order_by('order', 'created_at')
        return Response([section_to_dict(s, request) for s in sections])

    # POST
    data = request.data
    section_type = data.get('section_type')
    title = data.get('title', '')

    if not section_type:
        return Response(
            {'error': 'section_type is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if section_type not in VALID_SECTION_TYPES:
        return Response(
            {'error': f'section_type must be one of: {", ".join(VALID_SECTION_TYPES)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    max_order = proposal.sections.aggregate(
        max_order=Max('order')
    )['max_order'] or 0

    section = ProposalSection.objects.create(
        proposal=proposal,
        section_type=section_type,
        title=title or dict(ProposalSectionType.choices).get(section_type, section_type.replace('_', ' ').title()),
        content=data.get('content') or {},
        order=max_order + 1,
    )
    return Response(section_to_dict(section, request), status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def proposal_section_reorder(request, slug, proposal_id):
    """Bulk update section order."""
    workspace = get_object_or_404(Workspace, slug=slug, owner=request.user)
    proposal = get_object_or_404(Proposal, id=proposal_id, workspace=workspace)

    data = request.data
    section_ids = data.get('section_ids')
    if not section_ids or not isinstance(section_ids, list):
        return Response(
            {'error': 'section_ids array is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    for order, sid in enumerate(section_ids):
        try:
            section = proposal.sections.get(id=sid)
            section.order = order
            section.save()
        except (ProposalSection.DoesNotExist, ValueError, TypeError):
            pass

    sections = proposal.sections.all().order_by('order', 'created_at')
    return Response([section_to_dict(s, request) for s in sections])


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def proposal_section_detail(request, slug, proposal_id, section_id):
    """Get, update, or delete a section."""
    workspace = get_object_or_404(Workspace, slug=slug, owner=request.user)
    proposal = get_object_or_404(Proposal, id=proposal_id, workspace=workspace)
    section = get_object_or_404(ProposalSection, id=section_id, proposal=proposal)

    if request.method == 'GET':
        return Response(section_to_dict(section, request))

    if request.method == 'DELETE':
        if section.section_type == ProposalSectionType.COVER_PAGE:
            return Response(
                {'error': 'The cover page cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        section.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH - title and content only; section_type fixed after creation
    data = request.data
    if 'title' in data:
        section.title = data['title']
    if 'content' in data:
        section.content = data['content'] if isinstance(data['content'], dict) else {}
    section.save()
    return Response(section_to_dict(section, request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def proposal_section_media_upload(request, slug, proposal_id, section_id):
    """Upload an image for a proposal section (signature, team photo, etc.)."""
    workspace = get_object_or_404(Workspace, slug=slug, owner=request.user)
    proposal = get_object_or_404(Proposal, id=proposal_id, workspace=workspace)
    section = get_object_or_404(ProposalSection, id=section_id, proposal=proposal)

    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response(
            {'error': 'No file provided. Use form field "file".'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        validate_image_file(file_obj)
    except ValidationError as e:
        return Response(
            {'error': validation_error_message(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    ext = os.path.splitext(getattr(file_obj, 'name', '') or '')[1].lstrip('.').lower()
    if ext not in {'jpg', 'jpeg', 'png', 'webp', 'avif'}:
        ext = 'png'
    filename = f'proposal_sections/{proposal_id}/{section_id}/{uuid.uuid4().hex[:12]}.{ext}'
    saved_name = default_storage.save(filename, file_obj)
    url = default_storage.url(saved_name)
    if request and url.startswith('/'):
        url = request.build_absolute_uri(url)
    return Response({'url': url})
