# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Billing module: plan configuration, limit checks, billing service, and exceptions."""

from assemblix_api.enums import PlanTier

from .credit_service import CreditService, InsufficientCreditsError
from .exceptions import BillingLimitExceeded, FeatureNotAvailable
from .limits import check_agents_limit, check_feature_available, get_plan_limits_info
from .plans import CreditConfig, PlanConfig, credit_config, get_plan_config
from .service import BillingService

__all__ = [
    "BillingService",
    "CreditService",
    "InsufficientCreditsError",
    "BillingLimitExceeded",
    "FeatureNotAvailable",
    "PlanConfig",
    "CreditConfig",
    "credit_config",
    "PlanTier",
    "get_plan_config",
    "check_agents_limit",
    "check_feature_available",
    "get_plan_limits_info",
]
