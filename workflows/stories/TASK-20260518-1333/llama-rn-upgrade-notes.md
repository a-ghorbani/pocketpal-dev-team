# llama.rn 0.12.1 PR Notes

## Upgrade

- Bump `llama.rn` from `0.12.0-rc.9` to `0.12.1`.
- Refresh lockfiles and iOS pods so the app consumes the 0.12.1 native artifacts on both platforms.

## Itemized llama.cpp change summary vs shipped version

PocketPal was shipping `llama.rn@0.12.0-rc.9`, which vendors llama.cpp at `b8827`.
`llama.rn@0.12.1` moves that vendored runtime through `b9084` and then `b9204`.

- Structured output fix: upstream `llama.rn` explicitly fixed `response_format` propagation through chat formatting (`4e9e667`), which is the bug this upgrade is meant to address.
- New decoding/runtime infrastructure: the vendored llama.cpp range adds speculative decoding support plus new `fit`, `ngram-cache`, `ngram-map`, and `ngram-mod` helpers in `cpp/common/`.
- Chat/template stack refresh: the range rewrites large parts of `chat.cpp`, `chat-auto-parser-generator.cpp`, `chat-peg-parser.cpp`, and related Jinja/value plumbing, which is directly relevant to JSON schema and tool/format constrained generation.
- OpenCL backend expansion: the range significantly expands `ggml-opencl` with new MoE, IQ4_NL, q4/q5/q8 noshuffle kernels and broader kernel refactors, so Android GPU paths pick up a materially newer backend.
- Hexagon backend expansion: the range adds new HTP operators (`diag`, `fill`, `solve-tri`, `gated-delta-net`, `hmx-flash-attn`) and related backend plumbing, improving the Qualcomm NPU execution surface.
- Multimodal/model coverage growth: the vendored llama.cpp tree adds or expands support for models/features such as `deepseek2ocr`, `glm-dsa`, `granite-moe`, `hunyuan-vl`, `jina-bert-v2/v3`, `lfm2moe`, `mamba2`, `mimo2`, `minicpm`, `mistral4`, `nemotron-h-moe`, `nomic-bert`, `phimoe`, and newer Qwen/Gemma family updates.
- MTMD/audio-vision surface growth: `cpp/tools/mtmd` picks up new model handlers including `granite-speech`, `mimovl`, and `yasa2`, along with broader clip/audio helper changes.
- Init responsiveness fix: upstream `llama.rn` also landed `fix(cpp, jsi): avoid blocking ui during backend init` (`09e69c2`), which reduces startup risk around backend initialization.

## Verification

- `yarn typecheck`
- Structured-output regression path:
  `FIREBASE_FUNCTIONS_URL=https://placeholder-firebase-functions.com SUPABASE_URL=https://example.supabase.co SUPABASE_ANON_KEY=test-key PALSHUB_API_BASE_URL=https://palshub.ai APPCHECK_DEBUG_TOKEN_ANDROID=test APPCHECK_DEBUG_TOKEN_IOS=test GOOGLE_IOS_CLIENT_ID=test GOOGLE_WEB_CLIENT_ID=test ENABLE_PALSHUB_INTEGRATION=true ENABLE_AUTHENTICATION=true ENABLE_OFFLINE_MODE=true APP_URL=pocketpal://app yarn test src/hooks/__tests__/useStructuredOutput.test.ts --runInBand --coverage=false`
- Android native build: `yarn build:android`
- iOS native dependency refresh: `bundle install` then `bundle exec pod install`
- iOS simulator build: Bundler-backed `xcodebuild ... | bundle exec xcpretty`

## Notes

- The first targeted Jest run failed because this repo's test environment expects `@env` symbols even when Babel test mode disables the dotenv transform. Re-running with explicit placeholder env vars validated the structured-output path successfully.
