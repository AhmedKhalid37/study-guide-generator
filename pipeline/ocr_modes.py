"""Pure, deterministic OCR/extraction **mode + cost/budget skeleton** (Slice 37).

This is a *framework* slice, not a provider slice. It gives later visual-manifest
and provider slices a single, safe place to express:

- **what extraction mode** the operator is in (`local_private` /
  `smart_cloud_assist` / `maximum_fidelity` — the Slice 36 mode vocabulary), and
- **what that mode means for budget/cost** (page caps, dollar caps, and an
  *advisory* per-page cost estimate for a future cloud document provider).

It does **nothing** to extraction. In particular this module:

- **Never calls a provider.** It imports nothing from PyMuPDF (``fitz``),
  Tesseract, ``pipeline.ocr_provider``, Mistral/Chandra/Gemini SDKs, or provider
  settings. It is pure stdlib (``dataclasses`` + ``typing``) so it can be unit
  tested with zero environment.
- **Never makes a network request** — pricing is a *static, documented snapshot*
  from ``docs/MISTRAL_OCR_VERIFICATION.md`` (a June 2026 estimate), not a live
  lookup and not billing truth.
- **Never enables cloud.** :func:`resolve_ocr_mode_config` produces a config in
  exactly the shape ``pipeline.ocr_routing.default_config()`` expects, and
  ``allow_cloud_ocr`` is ``False`` for the default mode AND for any cloud-capable
  mode **unless** an explicit ``cloud_opt_in=True`` setting is present. A mode
  name alone can never turn cloud on. Even when it is allowed, the Slice 33 policy
  only ever returns an *advisory* ``cloud_ocr_candidate`` — no cloud OCR is wired
  into extraction in this slice or that one.
- **Never leaks.** Every output field is a fixed token from a closed vocabulary,
  an int/float, ``None``, ``"USD"``, or the repo-relative ``price_source`` doc
  reference. No key, URL, ``Authorization`` header, host/model/executable path,
  socket path, argv, or raw provider message can survive into any output, because
  inputs are coerced field-by-field and never echoed.

Mapping to the rest of the OCR stack (see ``docs/HYBRID_OCR_DESIGN.md`` /
``docs/VISION_ROADMAP.md``)::

    OcrModeSettings ── resolve_ocr_mode_config ──▶ ocr_routing.default_config() shape
                    └─ estimate_ocr_cost ────────▶ advisory OcrCostEstimate (planning only)

Cost estimates are advisory and must be re-verified before any real billing UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

# --- Closed vocabularies ----------------------------------------------------
#
# Anything outside these sets is unknown-safe: it coerces to a default, never an
# error, and is never passed through into an output.

# Slice 36 extraction modes. The operator-facing strategy, not a provider id.
MODES = {
    "local_private",       # embedded text + local OCR only; no cloud, no consent
    "smart_cloud_assist",  # selective cloud document OCR on weak pages (opt-in)
    "maximum_fidelity",    # broad cloud extraction + future visual reasoning (opt-in)
}
DEFAULT_MODE = "local_private"

# Modes that *could* use a cloud provider — but only ever with explicit opt-in.
CLOUD_CAPABLE_MODES = {"smart_cloud_assist", "maximum_fidelity"}

# Provider *roles* — the slot a provider fills, independent of which id is chosen.
PROVIDER_ROLES = {
    "local_ocr_provider",     # runs on the box (tesseract_local today, chandra_local future)
    "cloud_document_provider",  # per-page cloud document extraction (mistral_ocr future)
    "cloud_vision_provider",  # optional future visual reasoning (vlm_*; not near-term)
}

# Provider *ids* — closed vocabulary. Only ``tesseract_local`` is implemented
# today (Slice 32); the rest are future roadmap ids named here so cost/budget
# planning has a stable token to reference. Naming an id here wires nothing.
PROVIDER_IDS = {
    "tesseract_local",  # current local OCR floor (implemented)
    "chandra_local",    # future high-quality local provider (not implemented)
    "mistral_ocr",      # future cloud document provider (not wired)
}

# How a provider bills. ``unknown`` is a first-class, safe state.
BILLING_UNITS = {"page", "token", "unknown"}

# Cost-estimate status — closed vocabulary, never a raw provider/billing message.
ESTIMATE_STATUSES = {
    "free",         # local provider; no cost
    "ok",           # a (still advisory) dollar estimate was produced
    "unavailable",  # no pricing snapshot for the resolved provider
    "unknown",      # could not resolve a provider at all
}

# Advisory estimate-warning tokens — fixed strings only.
ESTIMATE_WARNINGS = {
    "estimate_only",          # the dollar figure is a planning estimate, not billing
    "pricing_unavailable",    # provider has no known price snapshot
    "provider_not_configured",  # mode maps to a provider that isn't implemented/wired
    "exceeds_dollar_cap",     # estimate is above the operator's dollar cap (advisory)
    "page_cap_applied",       # billed page count was clamped to the page cap
    "selected_pages_clamped",  # selected_page_count exceeded total pages; clamped
}

# Repo-relative source note for the static price snapshot (NOT a host path/secret).
MISTRAL_PRICE_SOURCE = "docs/MISTRAL_OCR_VERIFICATION.md"
LOCAL_PRICE_SOURCE = "local"

# Which provider id a mode would route document extraction to. Local modes stay
# on the local floor; cloud-capable modes name the future cloud document provider
# (used for *planning* cost only — gated separately by ``cloud_opt_in``).
_MODE_DOCUMENT_PROVIDER = {
    "local_private": "tesseract_local",
    "smart_cloud_assist": "mistral_ocr",
    "maximum_fidelity": "mistral_ocr",
}


@dataclass(frozen=True)
class OcrProviderPricing:
    """A static, documented price snapshot for one provider id. Advisory only.

    ``unit_price_usd`` is per ``billing_unit`` (per page for the providers named
    here). ``batch_unit_price_usd`` is the optional cheaper batch tier. Local
    providers are free (``0.0``) and not estimates; the cloud provider price is a
    documented snapshot (``is_estimate=True``) with ``price_source`` pointing at
    the verification doc. No network, no key, no URL.
    """

    provider_id: str
    role: str
    billing_unit: str
    unit_price_usd: float
    batch_unit_price_usd: float | None
    is_estimate: bool
    price_source: str


# Static pricing snapshot. Cloud figures are the June 2026 estimate recorded in
# ``docs/MISTRAL_OCR_VERIFICATION.md`` ($2 / 1,000 pages standard, $1 / 1,000
# pages batch for Mistral OCR 3). Update *here* when re-verified — routing and
# extraction never read this table.
_PRICING: dict[str, OcrProviderPricing] = {
    "tesseract_local": OcrProviderPricing(
        provider_id="tesseract_local",
        role="local_ocr_provider",
        billing_unit="page",
        unit_price_usd=0.0,
        batch_unit_price_usd=None,
        is_estimate=False,
        price_source=LOCAL_PRICE_SOURCE,
    ),
    "chandra_local": OcrProviderPricing(
        provider_id="chandra_local",
        role="local_ocr_provider",
        billing_unit="page",
        unit_price_usd=0.0,
        batch_unit_price_usd=None,
        is_estimate=False,
        price_source=LOCAL_PRICE_SOURCE,
    ),
    "mistral_ocr": OcrProviderPricing(
        provider_id="mistral_ocr",
        role="cloud_document_provider",
        billing_unit="page",
        unit_price_usd=0.002,        # $2 / 1,000 pages (standard) — June 2026 estimate
        batch_unit_price_usd=0.001,  # $1 / 1,000 pages (batch) — June 2026 estimate
        is_estimate=True,
        price_source=MISTRAL_PRICE_SOURCE,
    ),
}


@dataclass(frozen=True)
class OcrModeSettings:
    """Operator OCR/extraction settings. Sanitized; safe to serialize.

    ``cloud_opt_in`` is the single explicit gate that lets a cloud-capable mode
    actually allow cloud routing — a mode name alone never does. ``page_cap`` and
    ``dollar_cap`` are advisory budget ceilings; ``selected_page_count`` is how
    many pages the operator chose to send (used for cost planning).
    """

    mode: str = DEFAULT_MODE
    cloud_opt_in: bool = False
    local_ocr_available: bool = True
    page_cap: int | None = None
    dollar_cap: float | None = None
    selected_page_count: int | None = None


@dataclass(frozen=True)
class OcrBudget:
    """A normalized budget view derived from settings. Advisory, JSON-safe."""

    page_cap: int | None
    dollar_cap: float | None
    selected_page_count: int | None


@dataclass(frozen=True)
class OcrCostEstimate:
    """An advisory, planning-only cost estimate. Never billing truth.

    Every field is a closed-vocab token, a number, ``None``, ``"USD"``, or the
    repo-relative ``price_source``. Produced without any network call.
    """

    mode: str
    provider_id: str | None
    provider_role: str | None
    billing_unit: str
    billed_page_count: int
    estimated_cost_usd: float | None
    currency: str
    is_estimate: bool
    status: str
    price_source: str | None
    warnings: list[str] = field(default_factory=list)


# --- public API -------------------------------------------------------------


def default_ocr_mode_settings() -> OcrModeSettings:
    """The privacy-first default: ``local_private``, cloud off, no caps."""
    return OcrModeSettings()


def resolve_ocr_mode_config(settings: Any = None) -> dict[str, Any]:
    """Map mode settings to a Slice 33 ``ocr_routing`` policy config.

    Returns a dict in exactly the shape :func:`pipeline.ocr_routing.default_config`
    expects (``allow_cloud_ocr``, ``local_ocr_available``, ``max_ocr_pages``,
    ``page_budget_remaining``), plus a non-authoritative ``mode`` echo that the
    routing core ignores.

    ``allow_cloud_ocr`` is ``True`` **only** when the mode is cloud-capable AND
    ``cloud_opt_in is True``. The default mode (``local_private``) and any
    cloud-capable mode without explicit opt-in both resolve to
    ``allow_cloud_ocr=False`` — local-first, cloud-off. Never raises.
    """
    s = _coerce_settings(settings)
    allow_cloud = s.mode in CLOUD_CAPABLE_MODES and s.cloud_opt_in is True
    return {
        "allow_cloud_ocr": allow_cloud,
        "local_ocr_available": s.local_ocr_available,
        "max_ocr_pages": s.page_cap,
        "page_budget_remaining": None,  # left to the runtime batch loop
        "mode": s.mode,  # advisory echo; ocr_routing ignores unknown keys
    }


def ocr_budget(settings: Any = None) -> OcrBudget:
    """Extract the advisory budget view from (sanitized) settings."""
    s = _coerce_settings(settings)
    return OcrBudget(
        page_cap=s.page_cap,
        dollar_cap=s.dollar_cap,
        selected_page_count=s.selected_page_count,
    )


def provider_pricing(provider_id: Any) -> OcrProviderPricing | None:
    """Return the static price snapshot for a provider id, or ``None`` if unknown."""
    if provider_id in _PRICING:
        return _PRICING[provider_id]
    return None


def estimate_ocr_cost(
    settings: Any = None,
    page_count: Any = 0,
    selected_page_count: Any = None,
) -> OcrCostEstimate:
    """Produce an advisory, planning-only cost estimate. Pure, total, never raises.

    The estimate describes what the mode's *document* provider would cost for the
    billed pages. It is a what-if for planning and does **not** imply cloud is
    enabled — :func:`resolve_ocr_mode_config` is the only thing that gates routing,
    and no cloud provider is wired into extraction in this slice.

    Billed pages = ``selected_page_count`` (arg overrides the settings value) when
    given, else ``page_count``; clamped to ``page_count`` and then to ``page_cap``.
    Local providers return ``status="free"`` with ``0.0``; the cloud document
    provider returns ``status="ok"`` with ``is_estimate=True``. If the resolved
    provider has no price snapshot, ``status="unavailable"``; if no provider can be
    resolved at all, ``status="unknown"``.
    """
    s = _coerce_settings(settings)
    total_pages = _safe_count(page_count, default=0)

    # selected: explicit arg wins, else the settings value.
    sel = selected_page_count if selected_page_count is not None else s.selected_page_count
    sel = _safe_count_or_none(sel)

    warnings: set[str] = set()

    billed = total_pages if sel is None else sel
    if sel is not None and sel > total_pages:
        billed = total_pages
        warnings.add("selected_pages_clamped")
    if s.page_cap is not None and billed > s.page_cap:
        billed = s.page_cap
        warnings.add("page_cap_applied")

    provider_id = _MODE_DOCUMENT_PROVIDER.get(s.mode)
    if provider_id is None:  # mode unknown despite coercion — defensive only
        return _unknown_estimate(s.mode, billed)

    pricing = _PRICING.get(provider_id)
    if pricing is None:
        warnings.add("provider_not_configured")
        warnings.add("pricing_unavailable")
        return OcrCostEstimate(
            mode=s.mode,
            provider_id=provider_id if provider_id in PROVIDER_IDS else None,
            provider_role=None,
            billing_unit="unknown",
            billed_page_count=billed,
            estimated_cost_usd=None,
            currency="USD",
            is_estimate=True,
            status="unavailable",
            price_source=None,
            warnings=_safe_warnings(warnings),
        )

    # Free local provider: exact, not an estimate.
    if not pricing.is_estimate and pricing.unit_price_usd == 0.0:
        return OcrCostEstimate(
            mode=s.mode,
            provider_id=pricing.provider_id,
            provider_role=pricing.role,
            billing_unit=pricing.billing_unit,
            billed_page_count=billed,
            estimated_cost_usd=0.0,
            currency="USD",
            is_estimate=False,
            status="free",
            price_source=pricing.price_source,
            warnings=_safe_warnings(warnings),
        )

    # Cloud document provider: advisory dollar estimate.
    cost = round(billed * pricing.unit_price_usd, 6)
    warnings.add("estimate_only")
    if s.dollar_cap is not None and cost > s.dollar_cap:
        warnings.add("exceeds_dollar_cap")
    return OcrCostEstimate(
        mode=s.mode,
        provider_id=pricing.provider_id,
        provider_role=pricing.role,
        billing_unit=pricing.billing_unit,
        billed_page_count=billed,
        estimated_cost_usd=cost,
        currency="USD",
        is_estimate=True,
        status="ok",
        price_source=pricing.price_source,
        warnings=_safe_warnings(warnings),
    )


def safe_ocr_mode_settings_dict(settings: Any = None) -> dict[str, Any]:
    """JSON-safe, whitelisted dict of mode settings. No secret/path can appear."""
    s = _coerce_settings(settings)
    return {
        "mode": s.mode,
        "cloud_opt_in": s.cloud_opt_in,
        "local_ocr_available": s.local_ocr_available,
        "page_cap": s.page_cap,
        "dollar_cap": s.dollar_cap,
        "selected_page_count": s.selected_page_count,
    }


def safe_ocr_cost_estimate_dict(estimate: OcrCostEstimate) -> dict[str, Any]:
    """JSON-safe, whitelisted dict for a cost estimate. Coerces every field."""
    return {
        "mode": estimate.mode if estimate.mode in MODES else DEFAULT_MODE,
        "provider_id": estimate.provider_id if estimate.provider_id in PROVIDER_IDS else None,
        "provider_role": estimate.provider_role if estimate.provider_role in PROVIDER_ROLES else None,
        "billing_unit": estimate.billing_unit if estimate.billing_unit in BILLING_UNITS else "unknown",
        "billed_page_count": _safe_count(estimate.billed_page_count, default=0),
        "estimated_cost_usd": estimate.estimated_cost_usd,
        "currency": "USD",
        "is_estimate": bool(estimate.is_estimate),
        "status": estimate.status if estimate.status in ESTIMATE_STATUSES else "unknown",
        "price_source": estimate.price_source,
        "warnings": _safe_warnings(estimate.warnings),
    }


def ocr_provider_pricing_snapshot() -> list[dict[str, Any]]:
    """Whitelisted, JSON-safe view of the static pricing snapshot (for docs/tests)."""
    out: list[dict[str, Any]] = []
    for pid in sorted(_PRICING):
        p = _PRICING[pid]
        out.append({
            "provider_id": p.provider_id,
            "role": p.role,
            "billing_unit": p.billing_unit,
            "unit_price_usd": p.unit_price_usd,
            "batch_unit_price_usd": p.batch_unit_price_usd,
            "is_estimate": p.is_estimate,
            "price_source": p.price_source,
        })
    return out


# --- internal sanitizers ----------------------------------------------------


def _coerce_settings(settings: Any) -> OcrModeSettings:
    """Coerce any input (OcrModeSettings / dict / None / junk) to safe settings.

    Never raises; every field falls back to its privacy-first default. Unknown
    keys are ignored, so a hostile dict cannot smuggle anything through.
    """
    base = OcrModeSettings()
    if isinstance(settings, OcrModeSettings):
        raw = {
            "mode": settings.mode,
            "cloud_opt_in": settings.cloud_opt_in,
            "local_ocr_available": settings.local_ocr_available,
            "page_cap": settings.page_cap,
            "dollar_cap": settings.dollar_cap,
            "selected_page_count": settings.selected_page_count,
        }
    elif isinstance(settings, dict):
        raw = settings
    else:
        return base

    return replace(
        base,
        mode=_safe_mode(raw.get("mode")),
        cloud_opt_in=_safe_bool(raw.get("cloud_opt_in"), default=False),
        local_ocr_available=_safe_bool(raw.get("local_ocr_available"), default=True),
        page_cap=_safe_count_or_none(raw.get("page_cap")),
        dollar_cap=_safe_dollar_or_none(raw.get("dollar_cap")),
        selected_page_count=_safe_count_or_none(raw.get("selected_page_count")),
    )


def _safe_mode(value: Any) -> str:
    """Closed-vocab mode, else the privacy-first default."""
    if value in MODES:
        return value  # type: ignore[return-value]
    return DEFAULT_MODE


def _safe_bool(value: Any, *, default: bool) -> bool:
    """Only a real bool counts; anything else uses ``default`` (no truthiness)."""
    if isinstance(value, bool):
        return value
    return default


def _safe_count(value: Any, *, default: int) -> int:
    """Non-negative int, else ``default``. Booleans rejected (they are ints)."""
    if isinstance(value, bool):
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _safe_count_or_none(value: Any) -> int | None:
    """Non-negative int, or ``None`` when unset/unparseable. Booleans rejected."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _safe_dollar_or_none(value: Any) -> float | None:
    """Non-negative float, or ``None``. Booleans/NaN/inf rejected."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return max(0.0, f)


def _safe_warnings(warnings: Any) -> list[str]:
    """Sorted list of in-vocab warning tokens only; anything else is dropped."""
    if not isinstance(warnings, (list, set, tuple)):
        return []
    return sorted({w for w in warnings if w in ESTIMATE_WARNINGS})


def _unknown_estimate(mode: str, billed: int) -> OcrCostEstimate:
    """Fixed safe estimate when no provider can be resolved for a mode."""
    return OcrCostEstimate(
        mode=mode if mode in MODES else DEFAULT_MODE,
        provider_id=None,
        provider_role=None,
        billing_unit="unknown",
        billed_page_count=_safe_count(billed, default=0),
        estimated_cost_usd=None,
        currency="USD",
        is_estimate=True,
        status="unknown",
        price_source=None,
        warnings=["pricing_unavailable", "provider_not_configured"],
    )
