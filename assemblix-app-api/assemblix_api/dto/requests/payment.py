# SPDX-License-Identifier: LicenseRef-Assemblix-EE
# Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
# MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
# it requires a valid commercial agreement with the copyright holder.
"""
Payment request DTOs
"""

from pydantic import Field

from assemblix_api.dto.base import DTOModel


class CreateSubscriptionRequest(DTOModel):
    target_plan: str = Field(
        ...,
        description="Target plan tier (free, starter, pro, business)",
    )
    is_recurrent: bool = Field(
        default=True,
        description="Bind the card for automatic renewal",
    )
