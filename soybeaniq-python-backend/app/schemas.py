from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class SupplierQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote_id: str
    supplier_id: str
    supplier_name: str
    supplier_type: Optional[str] = None
    quality: Optional[str] = None
    price_per_mt: float = Field(gt=0)
    transport_per_mt: float = Field(default=0, ge=0)
    available_mt: float = Field(ge=0)
    capacity_mt: Optional[float] = Field(default=None, ge=0)
    delivery_days: int = Field(default=0, ge=0)
    expires_on: Optional[str] = None
    moisture_pct: Optional[float] = Field(default=None, ge=0, le=100)
    foreign_matter_pct: Optional[float] = Field(default=None, ge=0, le=100)
    damaged_grain_pct: Optional[float] = Field(default=None, ge=0, le=100)

class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_mt: float = Field(gt=0, le=1_000_000)
    budget: Optional[float] = Field(default=None, gt=0)
    max_delivery_days: Optional[int] = Field(default=None, ge=0)
    required_supplier_type: Optional[str] = None
    required_quality: Optional[str] = None
    min_suppliers: int = Field(default=1, ge=1, le=20)
    max_suppliers: Optional[int] = Field(default=None, ge=1, le=20)
    max_moisture_pct: Optional[float] = Field(default=None, ge=0, le=100)
    max_foreign_matter_pct: Optional[float] = Field(default=None, ge=0, le=100)
    max_damaged_grain_pct: Optional[float] = Field(default=None, ge=0, le=100)
    quotes: list[SupplierQuote] = Field(min_length=1, max_length=500)

class Allocation(BaseModel):
    supplier_id: str
    quote_id: str
    supplier: str
    quantity_mt: float
    landed_cost_per_mt: float
    subtotal: float
    delivery_days: int

class OptimizeResponse(BaseModel):
    feasible: bool
    solver: str
    status: str
    required_mt: float
    allocated_mt: float
    unfilled_mt: float
    total_cost: Optional[float] = None
    avg_cost_per_mt: Optional[float] = None
    allocation: list[Allocation] = []
    excluded: list[dict] = []
    diagnostics: dict = {}
    warning: str = "Optimization is decision support; verify quality certificates, weights, taxes, contracts and delivery commitments before approval."
