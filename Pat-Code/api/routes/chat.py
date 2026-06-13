from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth.models import ChatRequest, ChatResponse
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    pat_service = request.app.state.pat_service

    try:
        result = await pat_service.chat(
            user_id=current_user["id"],
            message=body.message,
            conversation_id=body.conversation_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}")

    return ChatResponse(
        conversation_id=result["conversation_id"],
        response=result["response"],
    )
