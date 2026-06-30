# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.

"""Subscription plan limit checks."""

from assemblix_api.billing.exceptions import BillingLimitExceeded, FeatureNotAvailable
from assemblix_api.billing.plans import get_plan_config
from assemblix_api.enums import PlanTier


def check_agents_limit(
    plan: PlanTier, current_agents_count: int, source: str = "assemblix"
) -> None:
    """Check the agent (workflow) or widget count limit; None means unlimited."""
    if source == "chat":
        from assemblix_api.billing.plans import get_chat_plan_config

        chat_config = get_chat_plan_config(plan)
        max_limit = chat_config.max_widgets
        limit_type = "widgets"
        resource_name = "виджетов"
        plan_name = chat_config.name
    else:
        plan_config = get_plan_config(plan)
        max_limit = plan_config.max_agents
        limit_type = "agents"
        resource_name = "агентов"
        plan_name = plan_config.name

    if max_limit is None:
        return

    if current_agents_count >= max_limit:
        raise BillingLimitExceeded(
            detail=f"Достигнут лимит {resource_name} для плана {plan_name}: {max_limit}. "
            f"Обновите план для создания дополнительных {resource_name}.",
            limit_type=limit_type,
        )


def check_feature_available(plan: PlanTier, feature: str) -> None:
    """Check whether a feature is available on the given plan."""
    config = get_plan_config(plan)

    feature_mapping = {
        "project_variables": config.has_project_variables,
    }

    if feature not in feature_mapping:
        raise ValueError(f"Неизвестная фича: {feature}")

    if not feature_mapping[feature]:
        # Most gated features require PRO or higher
        required_plan = "PRO"
        raise FeatureNotAvailable(feature=feature, required_plan=required_plan)


def get_plan_limits_info(plan: PlanTier) -> dict:
    """Return a dict describing the plan's limits and features."""
    config = get_plan_config(plan)

    return {
        "plan": plan.value,
        "plan_name": config.name,
        "max_agents": config.max_agents,
        "credits_per_month": config.credits_per_month,
        "can_use_own_keys": config.can_use_own_keys,
        "has_project_variables": config.has_project_variables,
        "support_level": config.support_level,
    }
