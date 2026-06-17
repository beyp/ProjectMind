"""Fiscal Year utilities — debut 1er mars."""
import calendar
from datetime import date, timedelta
from typing import NamedTuple


class FiscalPeriod(NamedTuple):
    fy:      str
    quarter: str
    label:   str
    start:   date
    end:     date


def get_fiscal_year(d: date, start_month: int = 3) -> tuple:
    """
    Retourne (annee_fiscale, trimestre) pour une date.
    FY27 = 1 mars 2026 -> 28 fev 2027
    """
    fy      = d.year + 1 if d.month >= start_month else d.year
    offset  = (d.month - start_month) % 12
    quarter = (offset // 3) + 1
    return fy, quarter


def get_fiscal_period(d: date, start_month: int = 3) -> FiscalPeriod:
    """Retourne le FiscalPeriod complet pour une date."""
    fy, q    = get_fiscal_year(d, start_month)
    qsm      = ((q - 1) * 3 + start_month - 1) % 12 + 1
    qsy      = fy - 1 if qsm >= start_month else fy
    qs       = date(qsy, qsm, 1)
    end_month = qsm + 3
    if end_month > 12:
        qe = date(qsy + 1, end_month % 12 or 12, 1) - timedelta(days=1)
    else:
        qe = date(qsy, end_month, 1) - timedelta(days=1)
    return FiscalPeriod(
        fy      = f"FY{str(fy)[2:]}",
        quarter = f"Q{q}",
        label   = f"FY{str(fy)[2:]}-Q{q}",
        start   = qs,
        end     = qe,
    )


def get_fiscal_year_bounds(fy: int, start_month: int = 3) -> tuple:
    """Retourne (debut, fin) d une annee fiscale."""
    last_day = calendar.monthrange(fy, 2)[1]
    return date(fy - 1, start_month, 1), date(fy, 2, last_day)
