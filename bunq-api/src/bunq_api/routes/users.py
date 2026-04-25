import logging

from bunq.sdk.context.bunq_context import BunqContext
from bunq.sdk.model.generated.endpoint import UserApiObject
from fastapi import APIRouter, Request

router = APIRouter(prefix="/users", tags=["accounts"])
logger = logging.getLogger(__name__)


@router.get("/")
def list_users():
    logger.info("Fetching all users")
    users = UserApiObject.list().value
    return users


# @router.get("/{user_id}")
# def get_user(user_id: int):
#     user = UserApiObject.get(user_id).value
#     return user


@router.get("/me")
def get_current_user(request: Request):
    """Get the user associated with the current API key"""
    logger.info("Fetching current user")
    user_context = BunqContext.user_context()
    logger.debug("User context: %s", user_context.__dict__)
    return user_context.user_person
