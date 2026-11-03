"""Thin, local FastAPI boundary around the existing verified Python engine."""
from collections import OrderedDict
from datetime import date, time
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from core import live_generation
from core.models import ProposedPlan, StrictModel
from core.presentation import input_fingerprint, prepare_agent_result
from core.ui_input import build_day_context
from core.validator import detect_hard_conflicts, validate_plan

ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173",
           "http://127.0.0.1:4173", "http://localhost:4173")


class PendingActivity(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    start_time: time
    duration_minutes: int
    priority: Literal["high", "medium", "low"] = "medium"
    fixed: bool = False
    min_duration_minutes: int | None = None


class Interruption(StrictModel):
    label: str = Field(max_length=120)
    start_time: time
    end_time: time


class DayInput(StrictModel):
    date: date
    revision: int = Field(ge=0)
    now: time
    day_start: time
    day_end: time
    activities: list[PendingActivity] = Field(min_length=1, max_length=8)
    busy_windows: list[Interruption] = Field(default_factory=list, max_length=10)

    def context(self):
        return build_day_context(now=self.now, day_start=self.day_start, day_end=self.day_end,
                                 activities=[a.model_dump() for a in self.activities],
                                 busy_windows=[b.model_dump() for b in self.busy_windows])


class ValidationInput(StrictModel):
    day: DayInput
    proposal: ProposedPlan | None = None
    fingerprint: str | None = Field(default=None, min_length=64, max_length=64)


class RescueInput(StrictModel):
    day: DayInput
    request_id: UUID


def binding(day, context):
    # Clock advancement is revalidated, rather than pretending that time stopped.
    # All editable constraints, date and the local revision remain bound.
    return input_fingerprint(context.model_copy(update={"now_minute": 0}),
                             f"react:{day.date.isoformat()}:{day.revision}")


def safe_input_error(errors):
    # Do not echo request bodies, provider errors, arbitrary values or ctx objects.
    return JSONResponse(status_code=422, content={"code": "INVALID_INPUT",
        "message": "Check activity times, names, durations and the day window.",
        "fields": [".".join(str(p) for p in e["loc"]) for e in errors[:20]]})


def create_app():
    app = FastAPI(title="DayRescue local adapter", docs_url=None, redoc_url=None, openapi_url=None)
    lock = Lock()
    used_requests = OrderedDict()
    app.add_middleware(CORSMiddleware, allow_origins=list(ORIGINS),
                       allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-DayRescue-Action"], allow_credentials=False)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.url.hostname not in ("127.0.0.1", "localhost", "::1") or not request.client or request.client.host not in ("127.0.0.1", "::1"):
            return JSONResponse(status_code=403, content={"code": "LOCAL_ONLY", "message": "Use the local DayRescue app."})
        if request.method == "POST":
            if request.headers.get("origin") not in ORIGINS:
                return JSONResponse(status_code=403, content={"code": "ORIGIN_DENIED", "message": "Open the app from its expected local address."})
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse(status_code=415, content={"code": "JSON_REQUIRED", "message": "Send a JSON request."})
            length = request.headers.get("content-length", "0")
            if not length.isdigit() or int(length) > 65536:
                return JSONResponse(status_code=413, content={"code": "INPUT_TOO_LARGE", "message": "This request is too large."})
        try:
            response = await call_next(request)
        except Exception:
            return JSONResponse(status_code=500, content={"code": "SERVICE_ERROR", "message": "The local service could not complete the request. No plan was applied."})
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def request_errors(request, exc):
        return safe_input_error(exc.errors())

    @app.exception_handler(ValidationError)
    async def domain_errors(request, exc):
        return safe_input_error(exc.errors())

    @app.exception_handler(ValueError)
    async def time_errors(request, exc):
        return safe_input_error([{"loc": ["time"]}])

    @app.get("/api/health")
    def health():
        return {"status": "ok", "live_enabled": live_generation.live_ai_enabled(), "evidence": "muse"}

    @app.post("/api/validate")
    def validate(body: ValidationInput):
        context = body.day.context()
        fingerprint = binding(body.day, context)
        if body.proposal is not None:
            if body.fingerprint != fingerprint:
                raise HTTPException(409, "Inputs changed. Discard the stale proposal and review the current day.")
            validation = validate_plan(context, body.proposal)
            return {"fingerprint": fingerprint, "validation": validation.model_dump(),
                    "message": "Python checked this proposal against the current inputs and clock."}
        conflicts = detect_hard_conflicts(context)
        return {"fingerprint": fingerprint, "conflicts": [c.model_dump() for c in conflicts],
                "message": "Fixed conflicts detected." if conflicts else
                "No fixed conflicts detected. This is not proof of full feasibility or optimality."}

    @app.post("/api/rescue")
    def rescue(body: RescueInput, request: Request):
        if request.headers.get("X-DayRescue-Action") != "rescue":
            raise HTTPException(400, "Use the explicit Rescue my day action.")
        if not live_generation.live_ai_enabled():
            raise HTTPException(403, "Live AI is disabled in the server process. Your original plan is unchanged.")
        context = body.day.context()
        if not lock.acquire(blocking=False):
            raise HTTPException(409, "A rescue request is already running. No additional request was started.")
        try:
            now = monotonic()
            while used_requests and next(iter(used_requests.values())) < now - 600:
                used_requests.popitem(last=False)
            if body.request_id in used_requests:
                raise HTTPException(409, "This request was already submitted. No automatic retry was made.")
            used_requests[body.request_id] = now
            while len(used_requests) > 512:
                used_requests.popitem(last=False)
            result = live_generation.generate_live_result(context)
            view = prepare_agent_result(context, result)
            accepted = view.validated and result.plan is not None
            return {"fingerprint": binding(body.day, context), "status": view.status, "evidence": "muse",
                    "message": view.message, "plan": result.plan.model_dump() if accepted else None,
                    "validation": validate_plan(context, result.plan).model_dump() if accepted else None,
                    "conflicts": [c.model_dump() for c in detect_hard_conflicts(context)],
                    "issues": list(view.issues), "trace": list(view.trace),
                    "rationale": view.rationale if accepted else ""}
        finally:
            lock.release()

    return app


app = create_app()
