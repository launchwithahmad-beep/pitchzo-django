import uuid
from django.db import models
from django.conf import settings

from .validators import validate_portfolio_image


class TemplateCategory(models.TextChoices):
    BUSINESS = 'business', 'Business'
    MARKETING = 'marketing', 'Marketing'
    CREATIVE = 'creative', 'Creative'
    TECHNOLOGY = 'technology', 'Technology'
    FINANCE = 'finance', 'Finance'
    CONSULTING = 'consulting', 'Consulting'
    LEGAL = 'legal', 'Legal'
    HEALTHCARE = 'healthcare', 'Healthcare'
    EDUCATION = 'education', 'Education'
    SALES = 'sales', 'Sales'
    OPERATIONS = 'operations', 'Operations'
    DESIGN = 'design', 'Design'


class Template(models.Model):
    """Standalone proposal template. No relations to User, Workspace, or Client."""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(
        upload_to='templates/',
        validators=[validate_portfolio_image],
    )
    category = models.CharField(
        max_length=50,
        choices=TemplateCategory.choices,
    )
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class ProposalStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'
    VIEWED = 'viewed', 'Viewed'


class ProposalSentVia(models.TextChoices):
    MAIL = 'mail', 'Mail'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    LINK = 'link', 'Link'


class ProposalGenBy(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    AI = 'ai', 'AI'


class ProposalSectionType(models.TextChoices):
    """Strict allowlist of section types. No custom types allowed."""
    # Front Matter
    COVER_PAGE = 'cover_page', 'Cover Page'
    COVER_LETTER = 'cover_letter', 'Cover Letter'
    EXECUTIVE_SUMMARY = 'executive_summary', 'Executive Summary'
    # Strategy & Alignment
    PROBLEM_STATEMENT = 'problem_statement', 'Problem Statement'
    DISCOVERY_AUDIT_FINDINGS = 'discovery_audit_findings', 'Discovery/Audit Findings'
    PROJECT_GOALS_KPIS = 'project_goals_kpis', 'Project Goals & KPIs'
    # Execution & Scope
    PROPOSED_SOLUTION = 'proposed_solution', 'Proposed Solution'
    SCOPE_OF_WORK = 'scope_of_work', 'Scope of Work'
    OUT_OF_SCOPE = 'out_of_scope', 'Out of Scope'
    TECH_STACK_ARCHITECTURE = 'tech_stack_architecture', 'Tech Stack & Architecture'
    TIMELINE_SPRINTS = 'timeline_sprints', 'Timeline & Sprints'
    # Proof & Credibility
    RELEVANT_PORTFOLIO_CASE_STUDIES = 'relevant_portfolio_case_studies', 'Relevant Portfolio & Case Studies'
    TESTIMONIALS_REVIEWS = 'testimonials_reviews', 'Testimonials & Reviews'
    MEET_THE_TEAM = 'meet_the_team', 'Meet the Team'
    COMPANY_AGENCY_OVERVIEW = 'company_agency_overview', 'Company/Agency Overview'
    # Financials
    SERVICES = 'services', 'Services'
    PRICING_ESTIMATE_TIERS = 'pricing_estimate_tiers', 'Pricing & Estimate Tiers'
    PAYMENT_SCHEDULE = 'payment_schedule', 'Payment Schedule'
    EXPECTED_ROI_BUSINESS_CASE = 'expected_roi_business_case', 'Expected ROI & Business Case'
    ONGOING_MAINTENANCE_SUPPORT = 'ongoing_maintenance_support', 'Ongoing Maintenance & Support'
    # Closing & Legal
    NEXT_STEPS_CTA = 'next_steps_cta', 'Next Steps & CTA'
    FAQS = 'faqs', 'FAQs'
    TERMS_CONDITIONS_MSA = 'terms_conditions_msa', 'Terms, Conditions & MSA'
    ACCEPTANCE_ESIGNATURE = 'acceptance_esignature', 'Acceptance & E-Signature'


class TemplateSection(models.Model):
    """
    One section per section_type per template. Section type cannot be repeated within a template.
    content holds HTML for that section type.
    """
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name='template_sections',
    )
    section_type = models.CharField(
        max_length=80,
        choices=ProposalSectionType.choices,
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default='')  # HTML content for this section type
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'section_type']
        constraints = [
            models.UniqueConstraint(
                fields=('template', 'section_type'),
                name='unique_template_section_type',
            ),
        ]

    def __str__(self):
        return f"{self.template.title} – {self.get_section_type_display()}"


class ProposalCategory(models.TextChoices):
    DEVELOPMENT = 'development', 'Development'
    DESIGN = 'design', 'Design'
    MARKETING = 'marketing', 'Marketing'
    FINANCE = 'finance', 'Finance'
    HEALTHCARE = 'healthcare', 'Healthcare'
    EDUCATION = 'education', 'Education'
    E_COMMERCE = 'e-commerce', 'E-commerce'
    TECHNOLOGY = 'technology', 'Technology'


class PortfolioSource(models.TextChoices):
    UPLOADED = 'uploaded', 'Uploaded'
    FACEBOOK = 'facebook', 'Facebook'
    LINKEDIN = 'linkedin', 'LinkedIn'
    GITHUB = 'github', 'GitHub'
    LINK = 'link', 'Link'


class PortfolioType(models.TextChoices):
    DEVELOPMENT = 'development', 'Development'
    DESIGN = 'design', 'Design'
    MARKETING = 'marketing', 'Marketing'
    FINANCE = 'finance', 'Finance'
    HEALTHCARE = 'healthcare', 'Healthcare'
    EDUCATION = 'education', 'Education'
    E_COMMERCE = 'e-commerce', 'E-commerce'
    TECHNOLOGY = 'technology', 'Technology'
    OTHERS = 'others', 'Others'


def portfolio_image_upload_to(instance, filename):
    ext = filename.split('.')[-1].lower() if '.' in filename else 'png'
    return f'portfolios/{uuid.uuid4().hex[:12]}.{ext}'


def portfolio_extra_image_upload_to(instance, filename):
    ext = filename.split('.')[-1].lower() if '.' in filename else 'png'
    return f'portfolios/extra/{uuid.uuid4().hex[:12]}.{ext}'


class Portfolio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ImageField(
        upload_to=portfolio_image_upload_to,
        validators=[validate_portfolio_image],
    )
    title = models.CharField(max_length=255)
    type = models.CharField(
        max_length=50,
        choices=PortfolioType.choices,
        default=PortfolioType.OTHERS,
    )
    detail = models.CharField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)  # array of strings
    source = models.CharField(
        max_length=20,
        choices=PortfolioSource.choices,
        default=PortfolioSource.UPLOADED,
    )
    resource = models.CharField(max_length=500, blank=True, null=True)
    resource_link = models.URLField(blank=True, null=True)
    fetch_date = models.DateTimeField(auto_now_add=True)
    last_rsync = models.DateTimeField(null=True, blank=True)
    workspace = models.ForeignKey(
        'authapp.Workspace',
        on_delete=models.CASCADE,
        related_name='portfolios',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='portfolios',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class PortfolioImage(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='extra_images',
    )
    image = models.ImageField(
        upload_to=portfolio_extra_image_upload_to,
        validators=[validate_portfolio_image],
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']


class Proposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=ProposalStatus.choices,
        default=ProposalStatus.DRAFT,
    )
    sentvia = models.CharField(
        max_length=20,
        choices=ProposalSentVia.choices,
        default=ProposalSentVia.LINK,
    )
    genby = models.CharField(
        max_length=10,
        choices=ProposalGenBy.choices,
        default=ProposalGenBy.MANUAL,
    )
    company_name = models.CharField(max_length=255, blank=True, default='')
    category = models.CharField(
        max_length=50,
        choices=ProposalCategory.choices,
        default=ProposalCategory.TECHNOLOGY,
    )
    client = models.ForeignKey(
        'clientsapp.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals_sent',
    )
    workspace = models.ForeignKey(
        'authapp.Workspace',
        on_delete=models.CASCADE,
        related_name='proposals',
    )
    template = models.ForeignKey(
        Template,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
    )
    currency = models.CharField(max_length=10)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )
    total = models.DecimalField(max_digits=14, decimal_places=2)
    projects = models.ManyToManyField(
        'Portfolio',
        related_name='proposals',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ProposalSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    section_type = models.CharField(
        max_length=80,
        choices=ProposalSectionType.choices,
    )
    title = models.CharField(max_length=255)
    content = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.proposal.title} - {self.title}"
