from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.products import router as products_router
from app.api.v1.ledger import router as ledger_router
from app.api.v1.basalam import router as basalam_router
from app.api.v1.support import router as support_router
from app.api.v1.files import router as files_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(products_router)
api_router.include_router(ledger_router)
api_router.include_router(basalam_router)
api_router.include_router(support_router)
api_router.include_router(files_router)
