# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.15](https://github.com/nmamizerov/assemblix/compare/v0.2.14...v0.2.15) (2026-07-16)


### Bug Fixes

* use json response_format for gpt-4o-transcribe models ([a766111](https://github.com/nmamizerov/assemblix/commit/a766111ad7fcd49b3e5665c739d7e22c8e2f0cc5))
* use json response_format for gpt-4o-transcribe models ([3974b6e](https://github.com/nmamizerov/assemblix/commit/3974b6eb5e19189e32aa482c1eca1a24f6c7e01e))

## [0.2.14](https://github.com/nmamizerov/assemblix/compare/v0.2.13...v0.2.14) (2026-07-14)


### Features

* api-keys whoami returns the key's project ([6e3fb10](https://github.com/nmamizerov/assemblix/commit/6e3fb102c508981750f18b61be3fb749d3d06c69))
* api-keys whoami returns the key's project ([8826ec0](https://github.com/nmamizerov/assemblix/commit/8826ec0b161278cf3fb7c0bcbadeb9461d2818d8))
* default project_id from the API key (drop explicit param requirement) ([f07519f](https://github.com/nmamizerov/assemblix/commit/f07519f200311e5ecdfe947d36949679083d6eaa))
* default project_id from the API key on workflow/execution list+create ([7279281](https://github.com/nmamizerov/assemblix/commit/72792819db3f213dfe6f471c7de2a988ae28b8f5))

## [0.2.13](https://github.com/nmamizerov/assemblix/compare/v0.2.12...v0.2.13) (2026-07-14)


### Features

* add AuthContext and APIKeyService.resolve_context ([b2f6781](https://github.com/nmamizerov/assemblix/commit/b2f67817cd0249d9484c8e8cfa85a2f27336094e))
* add get_auth_context dependency resolving key project scope ([111c11c](https://github.com/nmamizerov/assemblix/commit/111c11c3a377936e180090a5b32cfc7b9e1884ad))
* add ProjectService.authorize_project_access with key scope check ([98ec9cb](https://github.com/nmamizerov/assemblix/commit/98ec9cbaa081564ea4e89ee90fbe5ada3b6c63cc))
* enforce API key project scope on api-key endpoints ([5175697](https://github.com/nmamizerov/assemblix/commit/5175697aa34204a6ef86724bbee70002ead62e11))
* enforce API key project scope on avatar and voice credential endpoints ([2f70e61](https://github.com/nmamizerov/assemblix/commit/2f70e619b9b3f0792e7426a9fa5d96051f7d7332))
* enforce API key project scope on credentials endpoints ([7e9a93a](https://github.com/nmamizerov/assemblix/commit/7e9a93ae866a69901d8973d523336f482b049022))
* enforce API key project scope on execution list and detail ([171623b](https://github.com/nmamizerov/assemblix/commit/171623b1ae7a8cc018016c624b4929dfc61b0477))
* enforce API key project scope on knowledge base / node template / notification routers ([c10ff8d](https://github.com/nmamizerov/assemblix/commit/c10ff8d7338d18c4e8d376150ebebc114152649d))
* enforce API key project scope on project detail/update/delete ([8bcffae](https://github.com/nmamizerov/assemblix/commit/8bcffae556af1b142accd487fe5118179e6cedb4))
* enforce API key project scope on session routers ([dc5ab3c](https://github.com/nmamizerov/assemblix/commit/dc5ab3c836d0452e6f7d257811af5684ff6280c0))
* enforce API key project scope on workflow endpoints ([7b37335](https://github.com/nmamizerov/assemblix/commit/7b373355d45de1759e37a0f884ac955d1bf32dc0))
* hard-scope project API keys to their project across the REST API ([8b87d0c](https://github.com/nmamizerov/assemblix/commit/8b87d0c818789e70709660d5a89a921216d416cb))


### Documentation

* plan to extend API key scoping to remaining routers ([73028d1](https://github.com/nmamizerov/assemblix/commit/73028d129c88bf5b15bff0a0ec9fa304a4586bc0))
* spec + plans for project API key scoping and MCP server ([d8e8972](https://github.com/nmamizerov/assemblix/commit/d8e89725ce1621e1a92ed1bb2611608e14f7ba53))

## [0.2.12](https://github.com/nmamizerov/assemblix/compare/v0.2.11...v0.2.12) (2026-07-12)


### Documentation

* point README docs link to app.assmblx.com/docs ([2329949](https://github.com/nmamizerov/assemblix/commit/2329949737d6630c33d6d3050f5dc9296dbb875b))
* restructure site into Home / Get started / Creating workflows ([91dcc8a](https://github.com/nmamizerov/assemblix/commit/91dcc8ad22dc699280de472a04b9c2ce426c7a2e))
* restructure site into Home / Get started / Creating workflows ([614489c](https://github.com/nmamizerov/assemblix/commit/614489c38f603d1f78d846aa70dc9cb05698c770))

## [0.2.11](https://github.com/nmamizerov/assemblix/compare/v0.2.10...v0.2.11) (2026-07-12)


### Bug Fixes

* **schema-builder:** english comments, make test target, docs for vitest gate ([903e311](https://github.com/nmamizerov/assemblix/commit/903e311591c78953520cefdc761e0f7713a021d0))
* **schema-builder:** preserve array item objects in responseSchema round-trip ([191dce3](https://github.com/nmamizerov/assemblix/commit/191dce319df0022e2bcdf599d9f936dd7ebe7a87))


### Documentation

* serve MkDocs under /docs via nginx, drop GitHub Pages ([4ad2a74](https://github.com/nmamizerov/assemblix/commit/4ad2a74e06226edb5ad4ff535743bbf34e6236ee))
* serve MkDocs under /docs via nginx, drop GitHub Pages ([d4c826d](https://github.com/nmamizerov/assemblix/commit/d4c826d42555757a99c5508c8e92932dc1c3980f))

## [0.2.10](https://github.com/nmamizerov/assemblix/compare/v0.2.9...v0.2.10) (2026-07-09)


### Features

* AI avatars + Yandex SpeechKit voice (TTS+STT) ([3e2afea](https://github.com/nmamizerov/assemblix/commit/3e2afea2b38ecc1f4fa3c06dcdce05d177c3606c))
* **voice:** add Yandex SpeechKit TTS+STT provider with data-driven realtime toggle ([c778b03](https://github.com/nmamizerov/assemblix/commit/c778b03ccc40d0991302fa6d5d4272d02137ee64))

## [0.2.9](https://github.com/nmamizerov/assemblix/compare/v0.2.8...v0.2.9) (2026-07-08)


### Features

* **avatars:** add ANAM_TOKEN credentials type ([20fd6b6](https://github.com/nmamizerov/assemblix/commit/20fd6b6ce3ce71cb4fb50b8e13aaf3b531a91811))
* **avatars:** AI avatar output modality (anam.ai, phase 3) ([e6019b2](https://github.com/nmamizerov/assemblix/commit/e6019b2fb42b5ec904f7a0a671f27401fd9cb0fc))
* **avatars:** anam adapter (list_avatars + mint_session_token) ([fe34df4](https://github.com/nmamizerov/assemblix/commit/fe34df4473c90ce4f881b7eee6572e4bfe7c4f93))
* **avatars:** anam credential mapping + avatar config types ([4fd5862](https://github.com/nmamizerov/assemblix/commit/4fd58629d9af0bb25dac12bb825872a4d778db86))
* **avatars:** anam_api_base_url setting ([4ed6af3](https://github.com/nmamizerov/assemblix/commit/4ed6af315053ef53cac0df438b906f15601c8f98))
* **avatars:** avatar picker in header + agent-node avatar output option ([71b4dcd](https://github.com/nmamizerov/assemblix/commit/71b4dcd2fb8a6f93b79695c6edae5029039849f7))
* **avatars:** avatar session hook + conversational wiring ([901034b](https://github.com/nmamizerov/assemblix/commit/901034bfba42b918c144f2ea27ac56bafab456d9))
* **avatars:** avatar-model RTK entity ([ec3f385](https://github.com/nmamizerov/assemblix/commit/ec3f3857f9971ebcc50c4be276d9f88e1f097f8a))
* **avatars:** AvatarRenderer interface + AnamRenderer ([0470a50](https://github.com/nmamizerov/assemblix/commit/0470a50782084c5dc468074b09cde35d8f73ae1a))
* **avatars:** BYO-only avatar API key resolver ([34221e1](https://github.com/nmamizerov/assemblix/commit/34221e1c27d90b42d0e0b6836cbfb58f3453e7df))
* **avatars:** data-driven avatar model catalog (anam) ([19ea2a1](https://github.com/nmamizerov/assemblix/commit/19ea2a17ee8e44199d71d6c65cd3f2d058b9a5d3))
* **avatars:** debounced server-side voice search in the picker ([616b50b](https://github.com/nmamizerov/assemblix/commit/616b50bd036cda0e46d955dd1203cd7161a707a1))
* **avatars:** discovery + session response DTOs ([f462468](https://github.com/nmamizerov/assemblix/commit/f462468412973dcb75ef4a938dd5469c803c06b1))
* **avatars:** discovery + workflow session-mint API ([67a7542](https://github.com/nmamizerov/assemblix/commit/67a7542238a81acb827eb676c2e01ea8e15af7da))
* **avatars:** expose workflow config on CRUD DTOs so avatar persona persists ([e175fff](https://github.com/nmamizerov/assemblix/commit/e175fff69d4a656c60e9b023f069c1b8d859f9e7))
* **avatars:** i18n keys for avatar output (en/es/ru) + drop stray per-node avatar field ([60bae4c](https://github.com/nmamizerov/assemblix/commit/60bae4cfb1a4c87888bffaacac42f56113177a68))
* **avatars:** provider dispatch for session minting ([37119ff](https://github.com/nmamizerov/assemblix/commit/37119fff27dceba0fdfbc74d70b8c37ac0f88a36))
* **avatars:** show output-format badge (voice/avatar) on the agent node ([006c3dd](https://github.com/nmamizerov/assemblix/commit/006c3dd5b975ecd4c79c00f2aecbe17a3f383aea))
* **avatars:** tag avatar-node stream deltas for client forwarding ([73220fe](https://github.com/nmamizerov/assemblix/commit/73220fe50d78bbbe41821cd7e14dca23fd41b47d))
* **avatars:** workflow-global avatar config + avatar output_type ([4874fae](https://github.com/nmamizerov/assemblix/commit/4874fae32133367178184074f13bd786f72f76b4))


### Bug Fixes

* **avatars:** header tooltip key, optimistic avatar config, node warning ([1d42ad5](https://github.com/nmamizerov/assemblix/commit/1d42ad5d02ca3fb6613b5c4231f0da8231262fad))
* **avatars:** keep selected voice on search/node-edit + buffer first speech chunk ([4be07fb](https://github.com/nmamizerov/assemblix/commit/4be07fb620aac66c54ff65f1d7eddbdf457abb75))
* **avatars:** make avatar actually speak + user-initiated debug session ([c66904d](https://github.com/nmamizerov/assemblix/commit/c66904db9a49acb006023c7f43f7842e1b52f4ba))
* **avatars:** map anam avatar name from displayName/variantName (no 'name' field) ([cb971af](https://github.com/nmamizerov/assemblix/commit/cb971af7eadf28f9d9b082bd4d4c6b98e846786b))
* **avatars:** per-invocation epoch guard for avatar session connect race ([5a6a65c](https://github.com/nmamizerov/assemblix/commit/5a6a65cd77186a33e08eb55af8dbf8808f252750))
* **avatars:** require real avatarId+voiceId persona (anam dropped legacy tokens) ([9c2a706](https://github.com/nmamizerov/assemblix/commit/9c2a7063fb3a342da6dfcfce3acca6e9f15ab9a3))
* **avatars:** surface anam error body on session-mint/list failures ([f6769c7](https://github.com/nmamizerov/assemblix/commit/f6769c75fee48a10ffea91a23adb880cc7ab00b1))
* **avatars:** surface avatar connect errors + guard session lifecycle race ([7f23e59](https://github.com/nmamizerov/assemblix/commit/7f23e59b475ad8f49610962986e199d6ec69a957))
* **avatars:** warn when avatar output has streaming off + log talk-stream errors ([3975f3c](https://github.com/nmamizerov/assemblix/commit/3975f3c4bc8672cd76b6054db9e3c79917af9c11))


### Documentation

* **avatars:** phase-3 AI avatars design spec ([0ffcbd0](https://github.com/nmamizerov/assemblix/commit/0ffcbd0ecb14bc54fac0574c730b7de82a23283d))
* **avatars:** phase-3 implementation plan (16 TDD tasks) ([a7ac3a9](https://github.com/nmamizerov/assemblix/commit/a7ac3a94937d822a6640b582671ca09f15d10046))

## [0.2.8](https://github.com/nmamizerov/assemblix/compare/v0.2.7...v0.2.8) (2026-07-08)


### Features

* **voice-streaming:** agent voice helper (live gate, tee, buffered fallback, cost) ([007405c](https://github.com/nmamizerov/assemblix/commit/007405c7b1fd49a65e609eac48305d875f298fc8))
* **voice-streaming:** AgentNodeConfig output_type + voice + validation ([5b1ca64](https://github.com/nmamizerov/assemblix/commit/5b1ca649006be2401313d89889a8a0b74f882524))
* **voice-streaming:** AUDIO_DELTA event type + AlignmentData schema ([2e358b3](https://github.com/nmamizerov/assemblix/commit/2e358b37e4e6022d4afe21c37753a794a5dc9d18))
* **voice-streaming:** DebugEventManager.emit_audio_delta (transient) ([77f65e7](https://github.com/nmamizerov/assemblix/commit/77f65e789e27d0784ded95d2be05beec89843c52))
* **voice-streaming:** frontend — agent voice picker + Web Audio PCM player ([ad06570](https://github.com/nmamizerov/assemblix/commit/ad06570ba4ef4cae9833154ab8b6cb2ee58f02c2))
* **voice-streaming:** in-memory transient audio ring (live-only, no replay starvation) ([0e17a3b](https://github.com/nmamizerov/assemblix/commit/0e17a3b61181ef2745454d1054e433cdb350ba5b))
* **voice-streaming:** NodeInput.on_audio + node_runner PCM sink ([c115662](https://github.com/nmamizerov/assemblix/commit/c115662988821ba92faacfd756bde0548cfa076e))
* **voice-streaming:** realtime agent→TTS streaming voice output (phase 2b) ([a56cc21](https://github.com/nmamizerov/assemblix/commit/a56cc2164448598220a6724fc150871d575a2106))
* **voice-streaming:** realtime voice route + catalog entries ([769ddb5](https://github.com/nmamizerov/assemblix/commit/769ddb5e7ad23294cf5e6a74efc1e66d3678e41b))
* **voice-streaming:** RealtimeTTSSession EL stream-input client + fake WS seam ([88ca990](https://github.com/nmamizerov/assemblix/commit/88ca9908500c1005e9af584ad57a4ae3a76064b5))
* **voice-streaming:** Redis transient audio stream + seq-merged subscribe ([2948e4b](https://github.com/nmamizerov/assemblix/commit/2948e4b974ce0ddba19088537ed8e573f29efb69))
* **voice-streaming:** settings for realtime TTS + audio buffer ([976c924](https://github.com/nmamizerov/assemblix/commit/976c924663dfa0b8ea8f19e26d2f7587423c21d5))
* **voice-streaming:** wire live + buffered voice into AgentNode.execute ([504ece0](https://github.com/nmamizerov/assemblix/commit/504ece0e8abb24277295e4f2c97c7a1c97292d41))


### Bug Fixes

* **voice-streaming:** add agent voice i18n keys to ru/es locales (build green) ([45689a3](https://github.com/nmamizerov/assemblix/commit/45689a3f4627ba612571cc4325485f3f17488a17))


### Documentation

* **voice-streaming:** Phase 2b implementation plan (17 tasks, TDD) ([d666ada](https://github.com/nmamizerov/assemblix/commit/d666adaac4f8b70265d7df67e7670013dc222d02))
* **voice-streaming:** Phase 2b realtime agent→TTS design spec ([e77d1f1](https://github.com/nmamizerov/assemblix/commit/e77d1f1bc70a66b08ff43603f8923cba16b67796))
* **voice-streaming:** spike results — EL stream-input WS + Web Audio PCM ([0f54d20](https://github.com/nmamizerov/assemblix/commit/0f54d203ae619a8e9c9cb8ea121ac8f0acbf653e))


### Refactoring

* **voice-streaming:** remove synthesis from END (moved to agent) ([88fcd22](https://github.com/nmamizerov/assemblix/commit/88fcd22a7af76589bba447e6910558b5f597de0e))

## [0.2.7](https://github.com/nmamizerov/assemblix/compare/v0.2.6...v0.2.7) (2026-07-07)


### Features

* **streaming:** AgentRunner streams text deltas via event_stream_handler ([f815c94](https://github.com/nmamizerov/assemblix/commit/f815c94377eba305ca659fb008f71adffcff0fa9))
* **streaming:** buffer lifecycle - open_buffer (no queue) + TTL cleanup ([802772f](https://github.com/nmamizerov/assemblix/commit/802772f17ecc2aba2c0466ebd19235dbd7ea228b))
* **streaming:** buffer-backed DebugEventManager (emit_stream_delta/subscribe/is_streaming) ([ab11f46](https://github.com/nmamizerov/assemblix/commit/ab11f46b4c1c14a68070753952cfc243c183bed0))
* **streaming:** debug-runner streaming toggle + live token rendering ([8578def](https://github.com/nmamizerov/assemblix/commit/8578def018e3e7e9cfd2d99a75e9a74daa113869))
* **streaming:** GET /executions/{id}/stream SSE endpoint with cursor replay ([93fecf6](https://github.com/nmamizerov/assemblix/commit/93fecf676cda548d2443f70aa479918680048dae))
* **streaming:** in-memory sequence-numbered replayable stream buffer ([573a255](https://github.com/nmamizerov/assemblix/commit/573a255076e118f0da427b740d6c63c77ab74c78))
* **streaming:** litellm shim supports stream=True via _StreamShim ([93c8fae](https://github.com/nmamizerov/assemblix/commit/93c8fae9568f4a7fc74b04c427bccb04513dc4f6))
* **streaming:** per-node stream flag with three-gate delta emission ([1924417](https://github.com/nmamizerov/assemblix/commit/1924417e552ee17d6f7b539b7269f5175b1bf457))
* **streaming:** Redis Stream buffer backend with in-memory parity ([f68a30b](https://github.com/nmamizerov/assemblix/commit/f68a30bcd2cca9cc15a80df1d1c42c964f91301b))
* **streaming:** request stream flag threads to context and opens the buffer ([d95a940](https://github.com/nmamizerov/assemblix/commit/d95a9408399e09c6ae78929e4724b272244ffc60))
* **streaming:** STREAM_DELTA event type + seq on DebugEvent ([3efe2d0](https://github.com/nmamizerov/assemblix/commit/3efe2d0568e30295d25048fe8976fd9ee47be5b8))
* **streaming:** token-level text streaming, debug-first (Phase 2a) ([51aae65](https://github.com/nmamizerov/assemblix/commit/51aae65c50d57a3e6ee220a7502ef91cacf65925))


### Documentation

* **streaming:** Phase 2a text streaming design spec ([95fee0e](https://github.com/nmamizerov/assemblix/commit/95fee0eba9b9ba4d6f50c708131fbc68a465759d))
* **streaming:** Phase 2a text streaming implementation plan ([7a3ece6](https://github.com/nmamizerov/assemblix/commit/7a3ece68d478c4f4a3dfefe1cae87deaa6c7883a))

## [0.2.6](https://github.com/nmamizerov/assemblix/compare/v0.2.5...v0.2.6) (2026-07-06)


### Features

* **voice:** add direct ElevenLabs client (list voices + synthesize) ([c1883e1](https://github.com/nmamizerov/assemblix/commit/c1883e1fcc4a71ea2b565c3d20a0a73f274b3711))
* **voice:** add elevenlabs credential type and voice-output settings ([b11fd9f](https://github.com/nmamizerov/assemblix/commit/b11fd9ff9f9fa9eef425d8e4de45993ef841cd40))
* **voice:** add ElevenLabs credential type to the web UI ([108e4c1](https://github.com/nmamizerov/assemblix/commit/108e4c18256e7e93295f716c47a9682b8eabd1bb))
* **voice:** add per-character TTS cost helper ([587c188](https://github.com/nmamizerov/assemblix/commit/587c188cfa90c188bf7df8a01cdbafe7bd40a75c))
* **voice:** add provider-agnostic synthesize() seam ([6230b6c](https://github.com/nmamizerov/assemblix/commit/6230b6c2f4770b480d1e638272a9518992217a48))
* **voice:** add voice output config to the END node schema ([5376cba](https://github.com/nmamizerov/assemblix/commit/5376cbae0cd688974a5a81e2549399a3a30639cf))
* **voice:** configurable ElevenLabs base URL for proxy override ([8ab16ee](https://github.com/nmamizerov/assemblix/commit/8ab16ee98573e76fe7bc539f5314282ff14bbdc9))
* **voice:** itemize TTS spend as VOICE_USAGE credit transactions ([cb99997](https://github.com/nmamizerov/assemblix/commit/cb999975735d09d8f71b46dcfbe4ecd2d011c39f))
* **voice:** list ElevenLabs voices by credential ([0f285f7](https://github.com/nmamizerov/assemblix/commit/0f285f73430c86d6654d36eabaa4006ed7996089))
* **voice:** meter TTS at finalization and keep audio out of the DB ([b2f87b1](https://github.com/nmamizerov/assemblix/commit/b2f87b12ff08bddc894c68cf323cdf9a7d441d51))
* **voice:** play synthesized audio in the chat reply ([59d552a](https://github.com/nmamizerov/assemblix/commit/59d552a50340594ba89eae969c0347bdef105b48))
* **voice:** register ElevenLabs speech models and capability-filtered discovery ([ba68f0c](https://github.com/nmamizerov/assemblix/commit/ba68f0c07d59c1a8c5002e1d5fef82a7d5df17db))
* **voice:** server-side voice output on the END node (ElevenLabs TTS) ([7bc81d6](https://github.com/nmamizerov/assemblix/commit/7bc81d6b4f304652ec477ef8f3fe231b890a4f3d))
* **voice:** synthesize audio in the END node with char cap and billing facts ([a335e85](https://github.com/nmamizerov/assemblix/commit/a335e855c04e969c7c70c1c266457443a40b6333))
* **voice:** system-token voice list endpoint and END-form branch ([f911ed5](https://github.com/nmamizerov/assemblix/commit/f911ed55daa8b82a26e18150d15335be070cbb78))
* **voice:** text/voice output picker on the END node form ([ae4c9ca](https://github.com/nmamizerov/assemblix/commit/ae4c9ca9b9ea871654df998364d1f016ffe6c31c))
* **voice:** track TTS cost in dedicated voice buckets ([34079d5](https://github.com/nmamizerov/assemblix/commit/34079d53628ff702b4bc26cf24b2a99f33e47b8e))
* **voice:** voice-aware credential resolution with system-key fallback ([84ca9e8](https://github.com/nmamizerov/assemblix/commit/84ca9e892cc5849c9b3e415863394b4fd4ad8eac))
* **voice:** voice-model hooks for speech models and account voices ([a3464eb](https://github.com/nmamizerov/assemblix/commit/a3464ebcb07efb857f5188bbd5560c76660a3403))


### Bug Fixes

* **voice:** resolve lint gates, graceful voice fallback, and review nits ([c60bfe9](https://github.com/nmamizerov/assemblix/commit/c60bfe92db010a14e0085719da598059f0cb64c3))
* **voice:** searchable, fixed-height voice select on the END node ([9ef5c50](https://github.com/nmamizerov/assemblix/commit/9ef5c502fdda386a2fb77c6e1f55870ced209693))


### Documentation

* **voice:** document voice-output env vars and read them via os.getenv ([7fead94](https://github.com/nmamizerov/assemblix/commit/7fead94c0da231ab9337830f2a316b72f922a6cd))
* **voice:** spec and implementation plan for voice output on the END node ([ed41c78](https://github.com/nmamizerov/assemblix/commit/ed41c789dacb54ec56865288a82e64ed12af5b98))

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
