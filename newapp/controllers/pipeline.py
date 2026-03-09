"""Pipeline CRM views — list, kanban board, opportunity management."""
import json
from django.http import JsonResponse, HttpResponse
from django.db.models import Q as models_Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from newapp.models import (
    Pipeline, PipelineStage, Opportunity, OpportunityComment,
    PipelineAutomation, Organization, User, Tag
)


def pipeline_list(request):
    """Show all pipelines for the current org."""
    org_id = request.session.get('organization_id')
    if not org_id:
        return redirect('/login')

    pipelines = Pipeline.objects.filter(organization_id=org_id)
    # Annotate with contact count
    pipeline_data = []
    for p in pipelines:
        p.contact_count = Opportunity.objects.filter(pipeline=p).count()
        p.total_value = sum(
            o.opportunity_value for o in Opportunity.objects.filter(pipeline=p)
        )
        pipeline_data.append(p)

    return render(request, 'pipeline/list.html', {
        'pipelines': pipeline_data,
    })


def pipeline_board(request, pipeline_id):
    """Kanban board view for a pipeline."""
    org_id = request.session.get('organization_id')
    if not org_id:
        return redirect('/login')

    pipeline = get_object_or_404(Pipeline, id=pipeline_id, organization_id=org_id)
    stages = pipeline.stages.all().order_by('order')

    search = request.GET.get('search', '')

    stage_data = []
    for stage in stages:
        opps = stage.opportunities.filter(status='open').select_related('user')
        if search:
            from django.db.models import Q
            opps = opps.filter(
                Q(user__name__icontains=search) |
                Q(user__phone_no__icontains=search) |
                Q(title__icontains=search)
            )
        stage.opp_list = list(opps)
        stage.opp_count = len(stage.opp_list)
        stage.total_value = sum(o.opportunity_value for o in stage.opp_list)
        stage_data.append(stage)

    # Contacts available to add as opportunity
    contacts = User.objects.filter(
        organization_id=org_id, is_in_inbox=True
    ).order_by('name')

    # Tags for automation UI
    from newapp.models import Tag
    admin_id = request.session.get('admin_id')
    tags = Tag.objects.filter(admin_id=admin_id) if admin_id else Tag.objects.none()

    # Automation rules
    automations = PipelineAutomation.objects.filter(
        pipeline=pipeline, is_active=True
    ).select_related('trigger_tag', 'target_stage')

    return render(request, 'pipeline/board.html', {
        'pipeline': pipeline,
        'stages': stage_data,
        'contacts': contacts,
        'search': search,
        'tags': tags,
        'automations': automations,
    })


@csrf_exempt
def pipeline_create(request):
    """Create a new pipeline with default stages."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    org_id = request.session.get('organization_id')
    if not org_id:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    name = data.get('name', 'New Pipeline')

    pipeline = Pipeline.objects.create(organization_id=org_id, name=name)

    # Create default stages
    defaults = [
        ('New Lead', '#6366f1', 0),
        ('Contacted', '#3b82f6', 1),
        ('Qualified', '#f59e0b', 2),
        ('Won', '#22c55e', 3),
        ('Lost', '#ef4444', 4),
    ]
    for sname, color, order in defaults:
        PipelineStage.objects.create(pipeline=pipeline, name=sname, color=color, order=order)

    return JsonResponse({'success': True, 'pipeline_id': pipeline.id})


@csrf_exempt
def pipeline_delete(request, pipeline_id):
    """Delete a pipeline and all its stages/opportunities."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    org_id = request.session.get('organization_id')
    pipeline = get_object_or_404(Pipeline, id=pipeline_id, organization_id=org_id)
    pipeline.delete()
    return JsonResponse({'success': True})


@csrf_exempt
def stage_create(request, pipeline_id):
    """Add a new stage to a pipeline."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    org_id = request.session.get('organization_id')
    pipeline = get_object_or_404(Pipeline, id=pipeline_id, organization_id=org_id)

    data = json.loads(request.body)
    name = data.get('name', 'New Stage')
    color = data.get('color', '#3b82f6')
    max_order = PipelineStage.objects.filter(pipeline=pipeline).count()

    stage = PipelineStage.objects.create(
        pipeline=pipeline, name=name, color=color, order=max_order
    )
    return JsonResponse({'success': True, 'stage_id': stage.id})


@csrf_exempt
def stage_delete(request, stage_id):
    """Delete a stage (moves opportunities to first stage)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    stage = get_object_or_404(PipelineStage, id=stage_id)
    pipeline = stage.pipeline

    # Move opportunities to first remaining stage
    first_stage = PipelineStage.objects.filter(pipeline=pipeline).exclude(id=stage_id).first()
    if first_stage:
        Opportunity.objects.filter(stage=stage).update(stage=first_stage)

    stage.delete()
    return JsonResponse({'success': True})


@csrf_exempt
def opportunity_create(request):
    """Create a new opportunity (contact card on board)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    org_id = request.session.get('organization_id')
    if not org_id:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    data = json.loads(request.body)
    pipeline_id = data.get('pipeline_id')
    stage_id = data.get('stage_id')
    user_id = data.get('user_id')
    title = data.get('title', '')
    value = data.get('value', 0)
    priority = data.get('priority', 'medium')

    pipeline = get_object_or_404(Pipeline, id=pipeline_id, organization_id=org_id)

    if not stage_id:
        stage = pipeline.stages.first()
    else:
        stage = get_object_or_404(PipelineStage, id=stage_id, pipeline=pipeline)

    opp = Opportunity.objects.create(
        pipeline=pipeline,
        stage=stage,
        user_id=user_id if user_id else None,
        organization_id=org_id,
        title=title,
        opportunity_value=value,
        priority=priority,
        created_by='Manual',
    )
    return JsonResponse({'success': True, 'opportunity_id': opp.id})


@csrf_exempt
def opportunity_move(request, opp_id):
    """Move opportunity to a different stage (drag-and-drop)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    new_stage_id = data.get('stage_id')

    opp = get_object_or_404(Opportunity, id=opp_id)
    new_stage = get_object_or_404(PipelineStage, id=new_stage_id)

    opp.stage = new_stage
    opp.save()

    return JsonResponse({'success': True})


@csrf_exempt
def opportunity_update(request, opp_id):
    """Update opportunity details."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    opp = get_object_or_404(Opportunity, id=opp_id)

    for field in ['title', 'description', 'priority', 'status']:
        if field in data:
            setattr(opp, field, data[field])
    if 'value' in data:
        opp.opportunity_value = data['value']
    if 'due_date' in data:
        opp.due_date = data['due_date'] or None

    opp.save()
    return JsonResponse({'success': True})


@csrf_exempt
def opportunity_delete(request, opp_id):
    """Delete an opportunity."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    opp = get_object_or_404(Opportunity, id=opp_id)
    opp.delete()
    return JsonResponse({'success': True})


@csrf_exempt
def opportunity_comment(request, opp_id):
    """Add a comment to an opportunity."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    text = data.get('text', '')

    if not text:
        return JsonResponse({'error': 'Comment text required'}, status=400)

    opp = get_object_or_404(Opportunity, id=opp_id)
    comment = OpportunityComment.objects.create(
        opportunity=opp, text=text, author='Admin'
    )
    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'text': comment.text,
            'author': comment.author,
            'created_at': comment.created_at.isoformat(),
        }
    })


@csrf_exempt
def stage_rename(request, stage_id):
    """Rename a pipeline stage."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)

    stage = get_object_or_404(PipelineStage, id=stage_id)
    stage.name = name
    stage.save()
    return JsonResponse({'success': True})


@csrf_exempt
def automation_create(request):
    """Create a pipeline automation rule."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    pipeline_id = data.get('pipeline_id')
    trigger_type = data.get('trigger_type')
    target_stage_id = data.get('target_stage_id')

    pipeline = get_object_or_404(Pipeline, id=pipeline_id)
    target_stage = get_object_or_404(PipelineStage, id=target_stage_id)

    auto = PipelineAutomation(
        pipeline=pipeline,
        trigger_type=trigger_type,
        target_stage=target_stage,
    )

    if trigger_type in ('tag_applied', 'tag_removed'):
        tag_id = data.get('trigger_tag_id')
        if tag_id:
            auto.trigger_tag_id = tag_id
    else:
        auto.trigger_field_name = data.get('trigger_field_name', '')
        auto.trigger_field_value = data.get('trigger_field_value', '')

    auto.save()
    return JsonResponse({'success': True, 'automation_id': auto.id})


@csrf_exempt
def automation_delete(request, auto_id):
    """Delete a pipeline automation rule."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    auto = get_object_or_404(PipelineAutomation, id=auto_id)
    auto.delete()
    return JsonResponse({'success': True})


def run_pipeline_automations(user_id, trigger_type, tag_id=None, field_name=None, field_value=None):
    """
    Called from tag/custom-field update views to check if any
    automation rule matches and auto-move the opportunity.
    Auto-creates an opportunity if none exists but a matching rule is found.
    """
    opps = Opportunity.objects.filter(user_id=user_id, status='open')
    
    # Build the matching rules query
    all_rules = PipelineAutomation.objects.filter(
        trigger_type=trigger_type,
        is_active=True,
    )
    
    if trigger_type in ('tag_applied', 'tag_removed') and tag_id:
        all_rules = all_rules.filter(trigger_tag_id=tag_id)
    elif trigger_type == 'custom_field_changed' and field_name:
        all_rules = all_rules.filter(trigger_field_name__iexact=field_name)
        if field_value:
            all_rules = all_rules.filter(
                models_Q(trigger_field_value='') | models_Q(trigger_field_value=field_value)
            )
    
    if not all_rules.exists():
        return
    
    if opps.exists():
        # Move existing opportunities
        for opp in opps:
            rules = all_rules.filter(pipeline=opp.pipeline)
            for rule in rules:
                opp.stage = rule.target_stage
                opp.save()
                print(f"[Automation] Moved opp {opp.id} to stage '{rule.target_stage.name}'")
                break
    else:
        # Auto-create opportunity in matching pipeline
        for rule in all_rules:
            try:
                user = User.objects.get(id=user_id)
                display_name = getattr(user, 'name', '') or user.phone_no
                opp = Opportunity.objects.create(
                    pipeline=rule.pipeline,
                    stage=rule.target_stage,
                    user=user,
                    name=f"{display_name}",
                    status='open'
                )
                print(f"[Automation] Created opp {opp.id} for user {user_id} in stage '{rule.target_stage.name}'")
                break  # Only create one opportunity
            except Exception as e:
                print(f"[Automation] Error creating opportunity: {e}")
