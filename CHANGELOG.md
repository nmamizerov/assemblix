# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.5](https://github.com/nmamizerov/assemblix/compare/v0.2.4...v0.2.5) (2026-07-06)


### Features

* **voice:** voice input via server-side transcription ([a07e5f2](https://github.com/nmamizerov/assemblix/commit/a07e5f22a8f9064c748676919c795aacfaabf144))
* **voice:** voice input via server-side transcription ([37e070c](https://github.com/nmamizerov/assemblix/commit/37e070c551e06a2835307de2843312362a1cf1bb))

## [0.2.4](https://github.com/nmamizerov/assemblix/compare/v0.2.3...v0.2.4) (2026-07-06)


### Features

* **execution:** parallel fork/join node execution within a run ([6443b5d](https://github.com/nmamizerov/assemblix/commit/6443b5dd1146a92ec3ce3f8a172a11aa2061f7d6))
* **execution:** parallel fork/join node execution within a run ([8ebda42](https://github.com/nmamizerov/assemblix/commit/8ebda4289b780ebb75e521f8d756f199109c1c07))


### Refactoring

* **execution:** extract per-node mechanics into NodeRunner ([b48318b](https://github.com/nmamizerov/assemblix/commit/b48318beb7d792ec90ca1e0cf1ee41761cfecb78))

## [0.2.3](https://github.com/nmamizerov/assemblix/compare/v0.2.2...v0.2.3) (2026-07-06)


### Bug Fixes

* **execution:** stop node self-loop from spinning to the cycle cap ([0c60188](https://github.com/nmamizerov/assemblix/commit/0c60188b3b62030035a68c87208c8da798040f65))

## [0.2.2](https://github.com/nmamizerov/assemblix/compare/v0.2.1...v0.2.2) (2026-07-05)


### Features

* **i18n:** add Spanish and Russian as selectable UI languages ([8930102](https://github.com/nmamizerov/assemblix/commit/8930102dd6a8cee53e07564ff6f9a9e6c9887636))
* **i18n:** add Spanish and Russian as selectable UI languages ([74f1393](https://github.com/nmamizerov/assemblix/commit/74f13934d12b8806000cc4588557e86fc2b4a9f4))

## [0.2.1](https://github.com/nmamizerov/assemblix/compare/v0.2.0...v0.2.1) (2026-07-05)


### Bug Fixes

* **agent:** always return all declared response-schema fields ([50db682](https://github.com/nmamizerov/assemblix/commit/50db68262417ecf2fc0901579dda2c30ab249ea0))
* **agent:** always return all declared response-schema fields ([eb54bc2](https://github.com/nmamizerov/assemblix/commit/eb54bc24bbfdf204524ada230e64c70cc7ba8627))
* **i18n:** force English for users with a stale non-bundled language ([ad432d5](https://github.com/nmamizerov/assemblix/commit/ad432d514b9c1dcf02de507a3f79dbb10a7d7d22))

## [0.2.0](https://github.com/nmamizerov/assemblix/compare/v0.1.12...v0.2.0) (2026-07-04)


### ⚠ BREAKING CHANGES

* GigaChat is no longer a supported LLM provider. Existing GigaChat credentials and agents referencing the gigachat provider will no longer resolve.

### Features

* **agent:** fallback credentials, save-to-history, LLM request view, system persona ([72047ee](https://github.com/nmamizerov/assemblix/commit/72047eed67e0a627bd24730a8398da13d69d936d))
* **agent:** fallback credentials, save-to-history, LLM request view, system persona ([373692f](https://github.com/nmamizerov/assemblix/commit/373692f8746451b12b7b9e87c04215196896eb63))
* remove GigaChat LLM provider ([a2ac3c7](https://github.com/nmamizerov/assemblix/commit/a2ac3c7c0ce6eb14b351e3ca6af143ddf77dc65b))


### Bug Fixes

* **api:** apply save_to_history/history_field to persisted session history ([f9851cc](https://github.com/nmamizerov/assemblix/commit/f9851ccb8bb4ef3f0e97d097500d8d740602df8c))
* **web:** gate the Assemblix system-key option, not the provider list ([4e8f1ec](https://github.com/nmamizerov/assemblix/commit/4e8f1ec618dec69b3869be754479511c2a5ec308))
* **web:** make node editor form scroll when content exceeds panel height ([22a490c](https://github.com/nmamizerov/assemblix/commit/22a490c37ad7ac3641c6fd0e6c05de114b88ea53))


### Refactoring

* **web:** stack fallback model fields vertically + advanced spacing ([dd7cc2f](https://github.com/nmamizerov/assemblix/commit/dd7cc2f2c00c3eae82cbde2f2169f995a249cad5))

## [0.1.12](https://github.com/nmamizerov/assemblix/compare/v0.1.11...v0.1.12) (2026-06-25)


### Documentation

* add vector "How it works" architecture diagram ([#31](https://github.com/nmamizerov/assemblix/issues/31)) ([4480084](https://github.com/nmamizerov/assemblix/commit/448008404bf4ea96129972c0c0c557e8d49df78c))

## [0.1.11](https://github.com/nmamizerov/assemblix/compare/v0.1.10...v0.1.11) (2026-06-23)


### Bug Fixes

* **api:** wait for queued execution result when task=false ([e38b1d6](https://github.com/nmamizerov/assemblix/commit/e38b1d6534d48321fc775eb768a19538cad825a5))
* **api:** wait for queued execution result when task=false ([7d9696e](https://github.com/nmamizerov/assemblix/commit/7d9696ef40eedb7ad920b35c90f9128c64c17ee7))


### Documentation

* add product screenshots to README gallery ([58ce878](https://github.com/nmamizerov/assemblix/commit/58ce8782c5f0af017291fada21463498745be9ad))

## [0.1.10](https://github.com/nmamizerov/assemblix/compare/v0.1.9...v0.1.10) (2026-06-22)


### Features

* **web:** billing gating, execution viewer panels, and UI fixes ([e82ab7c](https://github.com/nmamizerov/assemblix/commit/e82ab7c0cd25e86a74e8a7af4f768216a133fc4f))


### Documentation

* add hero demo GIF to README ([394e47e](https://github.com/nmamizerov/assemblix/commit/394e47e703c6e5e92796c81275722a8c65af672b))

## [0.1.9](https://github.com/nmamizerov/assemblix/compare/v0.1.8...v0.1.9) (2026-06-22)


### Features

* **web:** add 404 page, rename agent sessions, gate billing routes ([69be156](https://github.com/nmamizerov/assemblix/commit/69be156eb10db8c718d84f7039de63ed08d1931e))
* **web:** gate commercial billing UI behind VITE_BILLING_ENABLED ([8a00003](https://github.com/nmamizerov/assemblix/commit/8a000037a193d0cbda39a84517123d707305279f))
* **web:** OSS billing gating, 404 page & editor/panel UI fixes ([0cc2f71](https://github.com/nmamizerov/assemblix/commit/0cc2f71694164f0116b101dd80ae443bd05a3f39))


### Bug Fixes

* **web:** render custom nodes in panels and pin node-form headers ([0432288](https://github.com/nmamizerov/assemblix/commit/0432288984a4c5e9861182c4ee6ba8c8f3f8c718))

## [0.1.8](https://github.com/nmamizerov/assemblix/compare/v0.1.7...v0.1.8) (2026-06-22)


### Features

* **web:** execution viewer side panels with state diff ([f87ff80](https://github.com/nmamizerov/assemblix/commit/f87ff80ba3e8fdcc06c6c36f3d7d38b810ad635f))
* **web:** боковые панели в просмотре выполнения с диффом состояния ([24faf9c](https://github.com/nmamizerov/assemblix/commit/24faf9cf1de852d528fd5881f648f1b56f7b784f))

## [0.1.7](https://github.com/nmamizerov/assemblix/compare/v0.1.6...v0.1.7) (2026-06-22)


### Features

* **web:** remove docs & templates, make app domain flexible ([b3cec47](https://github.com/nmamizerov/assemblix/commit/b3cec47a41ae18aa7d314a55b6a6261f1ccd7416))
* **web:** remove docs & templates, make app domain flexible ([79b6841](https://github.com/nmamizerov/assemblix/commit/79b6841b43e625120380d14a5a922d3deb05e5b6))

## [0.1.6](https://github.com/nmamizerov/assemblix/compare/v0.1.5...v0.1.6) (2026-06-21)


### Features

* **api:** apply default plan to UI-created organizations too ([352352a](https://github.com/nmamizerov/assemblix/commit/352352a9fa3900fcfca0da66c92c6966dabce123))
* **api:** default new orgs to the unlimited BUSINESS plan on self-host ([6560378](https://github.com/nmamizerov/assemblix/commit/6560378f1832236080981b2ba7f2bf11e3f4407f))

## [0.1.5](https://github.com/nmamizerov/assemblix/compare/v0.1.4...v0.1.5) (2026-06-21)


### Features

* **api:** default new orgs to BUSINESS plan on self-host ([e47f246](https://github.com/nmamizerov/assemblix/commit/e47f246bd13433bdbf0a4ebedb56acfe29a4d2ba))
* **api:** default new orgs to BUSINESS plan on self-host ([a06d722](https://github.com/nmamizerov/assemblix/commit/a06d72236ad81df38357cbc89884434919a7610e))

## [0.1.4](https://github.com/nmamizerov/assemblix/compare/v0.1.3...v0.1.4) (2026-06-21)


### Features

* install.sh pins the latest release tag, not main ([ec9ce56](https://github.com/nmamizerov/assemblix/commit/ec9ce56b191a5bf3d783bdea718a15ba16c0d8de))
* install.sh pins the latest release tag, not the main branch ([ab3a642](https://github.com/nmamizerov/assemblix/commit/ab3a6426bc5eba076cc3b03170c7aef8baa4d431))


### Bug Fixes

* **web:** don't initialise Google/GitHub OAuth when no client ID is set ([68d8368](https://github.com/nmamizerov/assemblix/commit/68d8368900d53272bd213ced531bed7b4b7bde50))
* **web:** don't initialise OAuth when no client ID is configured ([d6e2fe5](https://github.com/nmamizerov/assemblix/commit/d6e2fe5e0a7cf749587d1f312bf234abcaf3bf94))

## [0.1.3](https://github.com/nmamizerov/assemblix/compare/v0.1.2...v0.1.3) (2026-06-21)


### Bug Fixes

* don't treat a commented-out REDIS_URL as enabled (breaks registration) ([6ea546e](https://github.com/nmamizerov/assemblix/commit/6ea546ec6f3d6815b579494f761fb08ad8ee4d26))
* don't treat a commented-out REDIS_URL as enabled (breaks registration) ([6b504dd](https://github.com/nmamizerov/assemblix/commit/6b504ddc1fa3f3883e05f0229f61ef04f3ee9f4d))

## [0.1.2](https://github.com/nmamizerov/assemblix/compare/v0.1.1...v0.1.2) (2026-06-21)


### Features

* one-command bootstrap installer (setup.sh + install.sh) ([aa1eae6](https://github.com/nmamizerov/assemblix/commit/aa1eae6960e1fa9721904155b202b20830582ca5))
* one-command bootstrap installer (setup.sh + install.sh) ([5d952aa](https://github.com/nmamizerov/assemblix/commit/5d952aa4acd4cbf3a27d9c3ea926b050fe390107))

## [0.1.1](https://github.com/nmamizerov/assemblix/compare/v0.1.0...v0.1.1) (2026-06-21)


### Features

* **api:** GET /api/nodes returns node descriptors ([c6e9cb1](https://github.com/nmamizerov/assemblix/commit/c6e9cb1d0a7deb9ebbdea162025dfee3ed7bf656))
* **nodes:** add capability hooks (input_source/is_terminal/branch/descriptor) to BaseNode ([ad79dd5](https://github.com/nmamizerov/assemblix/commit/ad79dd54a8ea15077b0ad70bc156dc803339c3a4))
* **nodes:** add DELAY node (SDK demonstrator, zero DB/schema changes) ([b4481fe](https://github.com/nmamizerov/assemblix/commit/b4481fec8d03e7e5e194d32ceb3b8067c1d76684))
* **nodes:** add NodeDescriptor declarative schema (n8n-style) ([50db105](https://github.com/nmamizerov/assemblix/commit/50db105888d9d483ffa2c291715f08ff2f4fd91c))
* **nodes:** built-in descriptors + START/END/CONDITION capability overrides ([b88a6df](https://github.com/nmamizerov/assemblix/commit/b88a6dfa6f7ffbd7b0ac92f12ae7443ebfffc6f0))
* **nodes:** entry-point plugin discovery (group assemblix.nodes) ([cd3d329](https://github.com/nmamizerov/assemblix/commit/cd3d329e9c3866ae3ab19edcfc2ba6477b1b8a20))
* **nodes:** GenericNode fallback so plugin node types round-trip through the API ([fdc8597](https://github.com/nmamizerov/assemblix/commit/fdc859781b411968d6bf77144207331e1332b12e))
* **nodes:** store execution_steps.node_type as varchar (enables plugin node types) ([10ff359](https://github.com/nmamizerov/assemblix/commit/10ff35952d0381f78d4a0710c4f79c56c076290e))
* **nodes:** string-keyed NodeRegistry with descriptor enumeration ([d08401f](https://github.com/nmamizerov/assemblix/commit/d08401fc43e91c7888ad9fde7f971ee921c2b767))
* **obs:** /metrics, /health, /ready probes (API + worker) ([6a20749](https://github.com/nmamizerov/assemblix/commit/6a2074937f7931209719beab2db3a50e30384a3b))
* **obs:** emit workflow/step/LLM metrics from the executor ([ede29c0](https://github.com/nmamizerov/assemblix/commit/ede29c0104a5fe8b7ceac84343505366304cc864))
* **obs:** GET /api/executions/in-flight + queue-depth gauge ([c4b5fd0](https://github.com/nmamizerov/assemblix/commit/c4b5fd062508fbc815dd6ff5986c33c3fa1ba001))
* **obs:** Prometheus metric definitions for workflow engine ([9cb5f7b](https://github.com/nmamizerov/assemblix/commit/9cb5f7bf02b9d59c3bca5ed705fe990b6c2b7299))
* **reliability:** Phase 3 — retries, fallbacks, timeouts on LLM/HTTP ([c74a910](https://github.com/nmamizerov/assemblix/commit/c74a910d78f9e53b34d089266eb7b8b736e22ecf))
* **reliability:** pure helpers to compute resume point from execution steps ([12cc761](https://github.com/nmamizerov/assemblix/commit/12cc761712eb98afc892b5036137b7b91b00d321))
* **reliability:** resume execution from last completed node when checkpointing enabled ([6fcedbe](https://github.com/nmamizerov/assemblix/commit/6fcedbe8c06324bbb8b32577e170225b61361606))
* **reliability:** worker re-enqueues orphaned executions on startup ([c14e3fc](https://github.com/nmamizerov/assemblix/commit/c14e3fc9b01cff78dc38a0603db5ff21eea7e165))
* **scale:** add Arq worker tier — queue package, enqueue helper, job, WorkerSettings ([3183a32](https://github.com/nmamizerov/assemblix/commit/3183a323fc7c80835f4809ef50b2e2aa135bb8f2))
* **scale:** add Arq worker, execution job, and enqueue helper ([25ada36](https://github.com/nmamizerov/assemblix/commit/25ada36dbe5efe97e3237d2bffef952b1e7ffa9d))
* **scale:** add BackgroundTaskRegistry + graceful shutdown timeout setting ([3b381af](https://github.com/nmamizerov/assemblix/commit/3b381af0ba8acbd2a2e4914672b39e3b816e3ff6))
* **scale:** add in-memory and Redis sliding-window rate-limit backends ([06d5dad](https://github.com/nmamizerov/assemblix/commit/06d5dad7853b95d2089566f330f9c37266405b01))
* **scale:** add optional Redis client, settings flags, and docker-compose service ([1d931fd](https://github.com/nmamizerov/assemblix/commit/1d931fdfff0acaf27a04b4edc7bbc4ee4c57f956))
* **scale:** add QUEUED execution status + migration ([a193a4f](https://github.com/nmamizerov/assemblix/commit/a193a4fa3fdeb76e81e26e99bdc9c412b9726ecb))
* **scale:** add Redis Pub/Sub transport for debug SSE events ([e99e8ef](https://github.com/nmamizerov/assemblix/commit/e99e8eff75ae6ee84b1ddead0774a447b1170dde))
* **scale:** executor can run a pre-created execution + repo finds orphans ([2bef5a9](https://github.com/nmamizerov/assemblix/commit/2bef5a956f5a952d66deb4b2bd96695d5e89d739))
* **scale:** make rate limiting async and backend-driven (Redis-capable) ([1a6acb1](https://github.com/nmamizerov/assemblix/commit/1a6acb1d571c6fd55dd3660c5b299158d309de3a))
* **scale:** route executions through Arq queue when EXECUTION_QUEUE_ENABLED ([fd86ac6](https://github.com/nmamizerov/assemblix/commit/fd86ac6ecb4d58eb5a8391018941e7fb2c039a7b))
* **scale:** stream debug SSE over Redis Pub/Sub when enabled ([d1676d1](https://github.com/nmamizerov/assemblix/commit/d1676d1889b9287b722241a33fb3a630193286b5))
* **scale:** track execution tasks and drain them on graceful shutdown ([09d60bd](https://github.com/nmamizerov/assemblix/commit/09d60bd646e34ede5d94717ff3481bd30a924f67))
* **security:** add per-IP brute-force rate limit on login and register ([8b3030a](https://github.com/nmamizerov/assemblix/commit/8b3030a01c302f7cd85a799c5faefe3cd5ec40b9))
* **web:** data-driven node forms (generic renderer + custom-widget escape hatch) ([2085918](https://github.com/nmamizerov/assemblix/commit/208591882bbc3bc4c44906a4a61c564196aefd0b))
* **web:** generic node-form field widgets ([fe83605](https://github.com/nmamizerov/assemblix/commit/fe83605eb673842af9ac1c12389a2663f9d2c58d))
* **web:** node descriptor types + useGetNodesQuery ([406fbf0](https://github.com/nmamizerov/assemblix/commit/406fbf0b3c12befc63b33e6c87af032a99af6190))


### Bug Fixes

* **descriptor:** add state_filter and project_filter to EndNode descriptor ([349bd08](https://github.com/nmamizerov/assemblix/commit/349bd08e0d9b79f378e0f3122dbadced71534a43))
* **inflight:** C1 QUEUED null started_at; stale registry/plugin docs ([9c583fb](https://github.com/nmamizerov/assemblix/commit/9c583fb2fba5bfb471975becc62effe39f3d4190))
* **llm,execution:** ssl_verify leak to OpenAI + QUEUED started_at NOT NULL ([912ebd5](https://github.com/nmamizerov/assemblix/commit/912ebd5e166f8033114ed21ddbac7210dcb5a7ba))
* **llm,execution:** ssl_verify leak to OpenAI + QUEUED started_at NOT NULL ([5ede4f9](https://github.com/nmamizerov/assemblix/commit/5ede4f9da209b1aa7d0fb36c9123335c867fb33b))
* **main:** replace misleading route-path metrics guard with module-level flag ([4866a94](https://github.com/nmamizerov/assemblix/commit/4866a94a0216f7de8d48ebe0e244ab2af7fa6058))
* **migration:** normalise execution_steps.node_type to lowercase after VARCHAR conversion ([b9c9af1](https://github.com/nmamizerov/assemblix/commit/b9c9af1d8605887accd5a5142683a56367df338f))
* **node-forms:** i18n placeholders and stable list keys (A10) ([55ea888](https://github.com/nmamizerov/assemblix/commit/55ea88852483a9bfd9020e074459debe0645c53f))
* **node:** remove dead ValidationError import; pass through GenericNode instances in _parse_node ([6e0ffb0](https://github.com/nmamizerov/assemblix/commit/6e0ffb00720b4438995fa866e11c66185259f40e))
* **nodes:** malformed built-in node config now raises instead of silently becoming GenericNode ([35d1aee](https://github.com/nmamizerov/assemblix/commit/35d1aeebbd036cb1f6440510c52722f9938355b8))
* **obs:** B5 review fixes — DTO type, service annotation, cross-tenant isolation test ([05c3817](https://github.com/nmamizerov/assemblix/commit/05c38174efd1eb4bc3bee2e32ac1440086ce6de1))
* **reliability:** guard FAILED-path step logging on resume; fix test has_step blindness ([f094d06](https://github.com/nmamizerov/assemblix/commit/f094d06ef48185941c464a8d092f160aceef075e))
* resolve frontend eslint and backend ruff violations ([5621849](https://github.com/nmamizerov/assemblix/commit/5621849cdc3d43d2b4aae0f60feb37376cb02c78))
* **scale:** call mark_running once for queued executions; type enqueue params ([470dc45](https://github.com/nmamizerov/assemblix/commit/470dc45c23dab42d810d5f6f88836f5305568268))
* **scale:** find_resumable also catches QUEUED rows with null started_at ([c1d2b14](https://github.com/nmamizerov/assemblix/commit/c1d2b14bae3e372a04c9629d92e823e659c34a68))
* **scale:** poll QUEUED as in-progress; harden Redis SSE (json guard + keepalive); Retry-After on login limit ([1bcce1d](https://github.com/nmamizerov/assemblix/commit/1bcce1d8f8431bb97a9727752990ecf99838dbce))
* **scale:** use unique sorted-set member per hit in Redis rate limiter ([1236b99](https://github.com/nmamizerov/assemblix/commit/1236b99efbda9eb339ffc37938b51508cb3ff4b6))
* **schemas:** remove unnecessary `from __future__ import annotations` from node.py ([f4a4bbb](https://github.com/nmamizerov/assemblix/commit/f4a4bbb9062e972eba771b7b8b3abf5a5ce21765))
* **security:** preserve 10/5min login limit, proxy-aware IP, remove dead limiter ([5a75ddf](https://github.com/nmamizerov/assemblix/commit/5a75ddffcfee04de0346b81c3d48b88db8de01c3))


### Performance

* **scale:** make DB pool env-configurable and raise defaults for worker tier ([02f3ec0](https://github.com/nmamizerov/assemblix/commit/02f3ec02d8401495db17490d7c194b96a56c07ec))


### Documentation

* add CONTRIBUTING_NODES.md (Node SDK guide) ([891c94a](https://github.com/nmamizerov/assemblix/commit/891c94af05ad5e1be2de7c7ed6ce2b67a82347a9))
* add Phase 5 implementation plan ([48d5399](https://github.com/nmamizerov/assemblix/commit/48d539928589ec9435599a787e198cda9fc05c2f))
* document observability endpoints + node SDK ([24d19de](https://github.com/nmamizerov/assemblix/commit/24d19de757d9250bb4d53564b28e9ae1746da5da))
* **nodes:** align entry-point format and descriptor return type in guide + loader ([f5ef705](https://github.com/nmamizerov/assemblix/commit/f5ef705cee5577dfeb23b5775de5fca2d5c5edeb))
* OSS launch — visual README, release automation, git workflow ([0b1ff06](https://github.com/nmamizerov/assemblix/commit/0b1ff06bb9f562ebc606eceb0a08ebfda0d85d5c))
* overhaul README and add OSS release automation + git workflow ([ed6b7c6](https://github.com/nmamizerov/assemblix/commit/ed6b7c6207c8cc5cde7524cde09768eb8e57ca09))
* **reliability:** address PR review — English comments + clearer rationale ([db0440a](https://github.com/nmamizerov/assemblix/commit/db0440a989e6ae980fe21adf859f62f263d3cdb5))
* **reliability:** trim verbose comments to concise one-liners ([6385958](https://github.com/nmamizerov/assemblix/commit/6385958964e1f50e8f07b0a64d7063c363d2669d))
* **scale:** add Phase 4 implementation plan ([e4ea712](https://github.com/nmamizerov/assemblix/commit/e4ea7126175fbae64ad9d307070b55890c979274))


### Refactoring

* **A11:** fix misleading comment and remove unused workflow prop from GenericNodeForm ([24f2732](https://github.com/nmamizerov/assemblix/commit/24f273242a2f8e0236f20c286d2c883d87d28114))
* **executor:** dispatch via node capability hooks, not hardcoded NodeType checks ([2e667db](https://github.com/nmamizerov/assemblix/commit/2e667db2c9df6150546cb75860a3d2594864ed4c))
* **llm:** address PR review — simplify, document, English comments ([8c4ebc4](https://github.com/nmamizerov/assemblix/commit/8c4ebc4f3fa0a14b4f72ea550070e27950a5a0e4))
* **llm:** Phase 2 step 1 — unified TemplateEvaluator + CI on all branches ([b17c70e](https://github.com/nmamizerov/assemblix/commit/b17c70ef04da5a1d9a7931bf53f44e25d4bdd49f))
* **llm:** Phase 2 step 2 — in-process LiteLLMModel adapter for Pydantic AI ([9b85052](https://github.com/nmamizerov/assemblix/commit/9b85052243064e864dbbd445a2aef1cf6bc48cd8))
* **llm:** Phase 2 step 3 — ToolRegistry + Pydantic AI toolsets + MCP seam ([eed3b7f](https://github.com/nmamizerov/assemblix/commit/eed3b7f4c8bc2f6628332990991a3428fc0334c3))
* **llm:** Phase 2 step 4 — AgentRunner over Pydantic AI + cost via model catalog ([9a8d48e](https://github.com/nmamizerov/assemblix/commit/9a8d48ee54c11c2f5a4a21e82f016d3ebb9c7bb5))
* **llm:** Phase 2 step 7 — delete the legacy provider/orchestrator layer ([b6944c5](https://github.com/nmamizerov/assemblix/commit/b6944c5d9a744ca9cef27dc639b2444d687d4cd8))
* **llm:** Phase 2 steps 5+6 — agent_node on Pydantic AI, billing decoupled ([607c11c](https://github.com/nmamizerov/assemblix/commit/607c11c547163a4df97d9b8a906c8dafaea5e7a9))
* **reliability:** narrow resume condition_index to int and DRY rebuild_state ([8d99c0c](https://github.com/nmamizerov/assemblix/commit/8d99c0ccf7b77334ba6dd1cd361838a809d73779))

## [Unreleased]

### Added
- Open-source community-health files: `LICENSE.md` (MIT + Commons Clause), `LICENSE_EE.md`
  (Enterprise), `NOTICE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  issue/PR templates, and `CODEOWNERS`.
- MkDocs documentation site.
- Frontend CI workflow (lint + type-check/build).

## [0.1.0] - 2026-06-20

Initial source-available release. Summary of the hardening work that preceded it:

### Added
- **CI & config foundation:** GitHub Actions pipeline (ruff, mypy, bandit SAST,
  pytest + coverage), repo-wide gitleaks secret scan, fail-fast validation of required
  secrets (`JWT_SECRET_KEY`, `ENCRYPTION_KEY`), and the single repo-root `.env` model.
- **Reliability:** retries with exponential backoff for LLM/HTTP/tool calls, model/provider
  fallback, explicit timeouts, and a transient-vs-fatal error taxonomy.
- **Scale (optional queue tier):** Redis-backed rate limiting, Arq worker tier, graceful
  shutdown, and execution persistence — all opt-in (`COMPOSE_PROFILES=queue`).
- **Extensibility:** Node SDK — nodes register by string type and are auto-discovered via
  the `assemblix.nodes` entry-point group; no core changes needed for custom nodes.
- **Observability:** Prometheus `/metrics`, `/health` and `/ready` probes, in-flight
  executions endpoint, and workflow/step/LLM metrics.

### Security
- SSRF protection in the HTTP-request node (blocks loopback/private/link-local, DNS-rebind
  safe), CEL evaluation timeout + expression limits, PDF parser size/page/timeout limits,
  brute-force rate limiting on `/login` and `/register`, configurable CORS, and a reduced
  JWT lifetime.
- Payment/billing endpoints gated behind `BILLING_ENABLED` (off by default for self-host).

[Unreleased]: https://github.com/nmamizerov/assemblix/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nmamizerov/assemblix/releases/tag/v0.1.0
