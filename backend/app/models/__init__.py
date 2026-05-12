"""
Re-export all ORM models so ``from app.models import *`` registers them all.
"""
from app.models.base import BaseModel, TimestampMixin, SoftDeleteMixin  # noqa: F401

# Import every model module to ensure they are registered on Base.metadata.
from app.db.models.user import User  # noqa: F401
from app.db.models.oauth_account import OAuthAccount  # noqa: F401
from app.db.models.transaction import Transaction, GeneralType, ReferenceType, TransactionStatus  # noqa: F401
from app.db.models.product import Product, ProductStatus  # noqa: F401
from app.db.models.product_image import ProductImage  # noqa: F401
from app.db.models.import_job import ImportJob, JobStatus  # noqa: F401
from app.db.models.support_ticket import SupportTicket, TicketStatus  # noqa: F401
from app.db.models.file import File, FileStatus  # noqa: F401

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    "User",
    "OAuthAccount",
    "Transaction",
    "GeneralType",
    "ReferenceType",
    "TransactionStatus",
    "Product",
    "ProductStatus",
    "ProductImage",
    "ImportJob",
    "JobStatus",
    "SupportTicket",
    "TicketStatus",
    "File",
    "FileStatus",
]
