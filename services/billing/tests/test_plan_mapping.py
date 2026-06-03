# tests/test_plan_mapping.py
from unittest.mock import MagicMock
from app.services.webhook_service import _get_plan_by_price_id, _get_plan_by_price_id_from_dict
from app.models import PlanEnum
from app.config import settings


class TestGetPlanByPriceId:
    def test_pro_price(self):
        sub = MagicMock()
        sub.items.data = [MagicMock(price=MagicMock(id=settings.STRIPE_PRO_PRICE_ID))]
        assert _get_plan_by_price_id(sub) == PlanEnum.pro

    def test_business_price(self):
        sub = MagicMock()
        sub.items.data = [MagicMock(price=MagicMock(id=settings.STRIPE_BUSINESS_PRICE_ID))]
        assert _get_plan_by_price_id(sub) == PlanEnum.business

    def test_unknown_price_returns_free(self):
        sub = MagicMock()
        sub.items.data = [MagicMock(price=MagicMock(id="price_unknown"))]
        assert _get_plan_by_price_id(sub) == PlanEnum.free

    def test_no_items_returns_free(self):
        sub = MagicMock()
        sub.items.data = []
        assert _get_plan_by_price_id(sub) == PlanEnum.free

    def test_missing_items_attr_returns_free(self):
        sub = MagicMock()
        sub.items = None
        assert _get_plan_by_price_id(sub) == PlanEnum.free


class TestGetPlanByPriceIdFromDict:
    def test_pro_price(self):
        d = {"items": {"data": [{"price": {"id": settings.STRIPE_PRO_PRICE_ID}}]}}
        assert _get_plan_by_price_id_from_dict(d) == PlanEnum.pro

    def test_business_price(self):
        d = {"items": {"data": [{"price": {"id": settings.STRIPE_BUSINESS_PRICE_ID}}]}}
        assert _get_plan_by_price_id_from_dict(d) == PlanEnum.business

    def test_unknown_price_returns_free(self):
        d = {"items": {"data": [{"price": {"id": "price_unknown"}}]}}
        assert _get_plan_by_price_id_from_dict(d) == PlanEnum.free

    def test_no_items_returns_free(self):
        d = {"items": {"data": []}}
        assert _get_plan_by_price_id_from_dict(d) == PlanEnum.free

    def test_missing_items_returns_free(self):
        d = {}
        assert _get_plan_by_price_id_from_dict(d) == PlanEnum.free

    def test_missing_price_id_returns_free(self):
        d = {"items": {"data": [{"price": {}}]}}
        assert _get_plan_by_price_id_from_dict(d) == PlanEnum.free
