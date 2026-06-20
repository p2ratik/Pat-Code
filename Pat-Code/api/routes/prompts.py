"""
Prompt management routes.

Endpoints:
    GET  /prompts              -> list all prompts
    POST /prompts              -> create a prompt (admin only)
    GET  /prompts/{id}         -> get a single prompt
    PATCH /prompts/{id}        -> update name / content / is_active (admin only)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth.models import PromptCreate, PromptResponse, PromptUpdate
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["prompts"])


@router.get("", response_model=list[PromptResponse])
async def list_prompts(request: Request, current_user: dict = Depends(get_current_user)):
    auth_service = request.app.state.auth_service
    prompts = await auth_service.list_prompts()
    return [PromptResponse(**p) for p in prompts]


@router.post("", response_model=PromptResponse)
async def create_prompt(
    body: PromptCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service

    # Only admins can create prompts.
    if not await auth_service.has_admin_role(current_user["id"]):
        raise HTTPException(status_code=403, detail="Only admins can create prompts")

    try:
        prompt = await auth_service.create_prompt(
            name=body.name,
            content=body.content,
            version=body.version,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PromptResponse(**prompt)


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service
    prompt = await auth_service.get_prompt(prompt_id)

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    return PromptResponse(**prompt)


@router.patch("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str,
    body: PromptUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service

    # Only admins can edit prompts.
    if not await auth_service.has_admin_role(current_user["id"]):
        raise HTTPException(status_code=403, detail="Only admins can update prompts")

    try:
        prompt = await auth_service.update_prompt(
            prompt_id=prompt_id,
            name=body.name,
            content=body.content,
            is_active=body.is_active,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    return PromptResponse(**prompt)
