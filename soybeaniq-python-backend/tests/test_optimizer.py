from datetime import date
from app.schemas import OptimizeRequest
from app.optimizer import optimize

def sample_request(**overrides):
    data = {
        "required_mt": 10,
        "budget": 130000,
        "min_suppliers": 2,
        "quotes": [
            {"quote_id":"q1","supplier_id":"s1","supplier_name":"Supplier One","price_per_mt":10000,"transport_per_mt":500,"available_mt":6,"capacity_mt":6,"delivery_days":2,"moisture_pct":10,"foreign_matter_pct":1,"damaged_grain_pct":1},
            {"quote_id":"q2","supplier_id":"s2","supplier_name":"Supplier Two","price_per_mt":11000,"transport_per_mt":300,"available_mt":8,"capacity_mt":8,"delivery_days":3,"moisture_pct":10,"foreign_matter_pct":1,"damaged_grain_pct":1}
        ]
    }
    data.update(overrides)
    return OptimizeRequest(**data)

def test_finds_feasible_multi_supplier_allocation():
    result = optimize(sample_request(), today=date(2026, 11, 17))
    assert result.feasible
    assert round(result.allocated_mt, 3) == 10
    assert len({x.supplier_id for x in result.allocation}) >= 2
    assert result.total_cost <= 130000

def test_reports_infeasible_budget():
    req = sample_request(budget=1000)
    result = optimize(req, today=date(2026, 11, 17))
    assert not result.feasible
    assert result.status == "INFEASIBLE"

def test_quality_filter_excludes_untested_quote():
    req = sample_request(max_moisture_pct=8)
    result = optimize(req, today=date(2026, 11, 17))
    assert not result.feasible
    assert all("moisture exceeds limit or is untested" in e["reasons"] for e in result.excluded)
