from __future__ import annotations
from datetime import date
from ortools.sat.python import cp_model
from .schemas import OptimizeRequest, OptimizeResponse, Allocation

SCALE_QTY = 1000       # 1 MT = 1,000 integer units (kg)
SCALE_MONEY = 100      # INR precision to paise

def _excluded_reason(q, r: OptimizeRequest, today: date) -> list[str]:
    reasons = []
    if q.available_mt <= 0: reasons.append("no availability")
    if q.capacity_mt is not None and q.capacity_mt <= 0: reasons.append("zero registered capacity")
    if q.capacity_mt is not None and q.available_mt > q.capacity_mt: reasons.append("quote exceeds registered supplier capacity")
    if q.delivery_days > (r.max_delivery_days if r.max_delivery_days is not None else 10**9): reasons.append("delivery deadline")
    if r.required_supplier_type and (q.supplier_type or "").strip().lower() != r.required_supplier_type.strip().lower(): reasons.append("supplier type")
    if r.required_quality and r.required_quality.strip().lower() not in (q.quality or "").lower(): reasons.append("quality specification")
    if r.max_moisture_pct is not None and (q.moisture_pct is None or q.moisture_pct > r.max_moisture_pct): reasons.append("moisture exceeds limit or is untested")
    if r.max_foreign_matter_pct is not None and (q.foreign_matter_pct is None or q.foreign_matter_pct > r.max_foreign_matter_pct): reasons.append("foreign matter exceeds limit or is untested")
    if r.max_damaged_grain_pct is not None and (q.damaged_grain_pct is None or q.damaged_grain_pct > r.max_damaged_grain_pct): reasons.append("damaged grain exceeds limit or is untested")
    if q.expires_on:
        try:
            if date.fromisoformat(q.expires_on) < today: reasons.append("expired quote")
        except ValueError:
            reasons.append("invalid quote expiry date")
    return reasons

def optimize(req: OptimizeRequest, today: date | None = None) -> OptimizeResponse:
    today = today or date.today()
    eligible, excluded = [], []
    for q in req.quotes:
        reasons = _excluded_reason(q, req, today)
        if reasons: excluded.append({"quote_id": q.quote_id, "supplier": q.supplier_name, "reasons": reasons})
        else: eligible.append(q)

    if not eligible:
        return OptimizeResponse(feasible=False, solver="OR-Tools CP-SAT", status="INFEASIBLE", required_mt=req.required_mt, allocated_mt=0, unfilled_mt=req.required_mt, excluded=excluded, diagnostics={"eligible_quotes": 0, "reason": "No quotations satisfy the requested filters."})

    # Integer quantities in kg; costs in paise per MT. All allocation quantities are divisible to 1 kg.
    model = cp_model.CpModel()
    demand_units = round(req.required_mt * SCALE_QTY)
    vars_by_quote = []
    supplier_to_indices: dict[str, list[int]] = {}
    for i, q in enumerate(eligible):
        upper_mt = min(q.available_mt, q.capacity_mt) if q.capacity_mt is not None else q.available_mt
        upper_units = max(0, round(upper_mt * SCALE_QTY))
        x = model.new_int_var(0, upper_units, f"qty_{i}")
        used = model.new_bool_var(f"used_{i}")
        model.add(x <= upper_units * used)
        model.add(x >= used)  # positive allocation if selected
        vars_by_quote.append((x, used))
        supplier_to_indices.setdefault(q.supplier_id, []).append(i)

    model.add(sum(x for x, _ in vars_by_quote) == demand_units)
    # If a supplier has multiple eligible quotes, count it once and cap aggregate quantity by its registered capacity.
    supplier_used = []
    for j, (supplier_id, indices) in enumerate(supplier_to_indices.items()):
        su = model.new_bool_var(f"supplier_used_{j}")
        quote_used = [vars_by_quote[i][1] for i in indices]
        model.add(sum(quote_used) >= su)
        model.add(sum(quote_used) <= len(indices) * su)
        caps = [eligible[i].capacity_mt for i in indices if eligible[i].capacity_mt is not None]
        if caps:
            supplier_cap = round(max(caps) * SCALE_QTY)
            model.add(sum(vars_by_quote[i][0] for i in indices) <= supplier_cap)
        supplier_used.append(su)
    model.add(sum(supplier_used) >= req.min_suppliers)
    if req.max_suppliers is not None: model.add(sum(supplier_used) <= req.max_suppliers)

    cost_terms = []
    for i, q in enumerate(eligible):
        cost_paise_per_mt = round((q.price_per_mt + q.transport_per_mt) * SCALE_MONEY)
        # x is kg, so cost coefficient is paise/kg; objective scaling is consistent across all quotes.
        cost_terms.append(vars_by_quote[i][0] * cost_paise_per_mt)
    total_cost_paise_times_kg = sum(cost_terms)
    if req.budget is not None:
        # Total INR = sum(kg * INR/MT) / 1000. Convert budget to paise*kg units.
        budget_limit = round(req.budget * SCALE_MONEY * SCALE_QTY)
        model.add(total_cost_paise_times_kg <= budget_limit)
    model.minimize(total_cost_paise_times_kg)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 8.0
    solver.parameters.num_search_workers = 8
    status = solver.solve(model)
    status_name = solver.status_name(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return OptimizeResponse(feasible=False, solver="OR-Tools CP-SAT", status=status_name, required_mt=req.required_mt, allocated_mt=0, unfilled_mt=req.required_mt, excluded=excluded, diagnostics={"eligible_quotes": len(eligible), "supplier_count_available": len(supplier_to_indices), "budget": req.budget, "reason": "No allocation satisfies all hard constraints. Check demand, budget, capacity, supplier count and quality filters."})

    allocations, total_cost, allocated = [], 0.0, 0.0
    for i, q in enumerate(eligible):
        units = solver.value(vars_by_quote[i][0])
        if units <= 0: continue
        qty = units / SCALE_QTY
        landed = q.price_per_mt + q.transport_per_mt
        subtotal = qty * landed
        allocations.append(Allocation(supplier_id=q.supplier_id, quote_id=q.quote_id, supplier=q.supplier_name, quantity_mt=qty, landed_cost_per_mt=landed, subtotal=subtotal, delivery_days=q.delivery_days))
        allocated += qty
        total_cost += subtotal
    return OptimizeResponse(feasible=True, solver="OR-Tools CP-SAT", status=status_name, required_mt=req.required_mt, allocated_mt=allocated, unfilled_mt=max(0, req.required_mt-allocated), total_cost=total_cost, avg_cost_per_mt=total_cost/allocated if allocated else None, allocation=allocations, excluded=excluded, diagnostics={"eligible_quotes": len(eligible), "supplier_count_used": len({a.supplier_id for a in allocations}), "objective_value_scaled": solver.objective_value, "best_bound_scaled": solver.best_objective_bound, "optimality_proven": status == cp_model.OPTIMAL, "quantity_granularity": "1 kg"})
