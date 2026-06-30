# Assemblix Enterprise License

Copyright (c) 2026 Nikita Mamizerov. All rights reserved.

> ⚠️ **Note:** This is a template commercial-license text. Have it reviewed by legal
> counsel before relying on it.

## Scope

This Enterprise License governs **only** the source files that carry the header:

```
SPDX-License-Identifier: LicenseRef-Assemblix-EE
```

These files implement Assemblix Enterprise functionality — currently the **billing /
credits subsystem** and the **payments / acquiring integration** (the Paddle
provider, the billing and payment API surface, the credits/plans logic, and the
corresponding frontend billing UI). All other files in this repository are licensed
under the [MIT + Commons Clause license](LICENSE.md) and are **not** subject to this
Enterprise License. Database migrations are intentionally **not** EE-licensed: the
open-source build must run the full migration chain to obtain a working schema.

The payments / acquiring features are disabled for self-hosting by default
(`BILLING_ENABLED=false`), and the `/payments` API router is not mounted in that mode.

## Grant

No rights are granted under this Enterprise License except as expressly agreed in a
separate written commercial agreement with the Licensor (Nikita Mamizerov). Absent such
an agreement, you may **not** use, run, copy, modify, distribute, sublicense, or create
derivative works of the Enterprise-licensed files, whether for production use, as a
hosted/managed service, or otherwise.

Reading the source for evaluation and security review is permitted.

## No warranty

THE ENTERPRISE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY ARISING FROM, OUT OF, OR IN CONNECTION WITH THE ENTERPRISE SOFTWARE.

## Contact

For commercial licensing inquiries: nmamizerov@gmail.com
