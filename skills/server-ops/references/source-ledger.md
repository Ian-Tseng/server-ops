# Related-Skill Source Ledger

Reviewed 2026-08-20. Popularity means either official ecosystem stewardship or public
GitHub adoption at review time; it does not imply correctness. External text was not
copied. The implementation adopts bounded design patterns and preserves its own contracts.

| Source | Snapshot and popularity signal | Adopted | Rejected or deferred |
|---|---|---|---|
| OpenAI Plugins: NVIDIA `aiq-deploy` skill | [`b197a8c`](https://github.com/openai/plugins/blob/b197a8c5f7e48e54871a76c109181654a0441216/plugins/nvidia/skills/aiq-deploy/SKILL.md); official OpenAI repository, 5,121 stars | route conditional detail to references; validate after startup; separate health from compatibility; do not print secrets; approve destructive cleanup | Docker, Helm, Kubernetes, credential configuration, and production deployment |
| Agno `extend-agent` skill | [`a9274fc`](https://github.com/agno-agi/agentos-railway/blob/a9274fcce21e16d06d50aac90ef940c17bdf7eec/.agents/skills/extend-agent/SKILL.md); active public implementation | prove the runtime is bound to the intended checkout before restart; health then targeted smoke test; label mutation-bearing probes | Compose-specific restart commands and database-mutating smoke tests |
| OpenAI Plugins: `agents-sdk` skill | [`f9c1205`](https://github.com/openai/plugins/blob/f9c120537a03fc6ae0134e3523f8f1e9d73f36e5/plugins/openai-developers/skills/agents-sdk/SKILL.md); official OpenAI repository, 5,121 stars | require deployable signals; let the lifecycle manager own records; verify manager/app/runtime separately; report generated files | automatic cloning/pulling, Docker-default deployment, and remote manager scope |
| Mode `skill-manager` | [`e306ba4`](https://github.com/mode-io/skill-manager/blob/e306ba4e3b7194a920ab3fce7e4ccea7b11a444d/README.md); 115 stars | one canonical package, source/install distinction, hashes, and refusal to overwrite untracked changed targets | background service, multi-harness management, MCP management, and network scanning |
| OpenAI `skill-creator` | [`4ab6e0f`](https://github.com/openai/skills/blob/4ab6e0fd99c6667163bc34173e3ed3a3fed75ebc/skills/.system/skill-creator/SKILL.md); official repository, 25,050 stars | precise trigger description, progressive disclosure, deterministic scripts, metadata parity, structural validation | generic boilerplate and unrelated assets |
| OpenAI Agents Python `runtime-behavior-probe` | [`9648a40`](https://github.com/openai/openai-agents-python/blob/9648a401a041919cef91fd68069ef2514708f10e/.agents/skills/runtime-behavior-probe/SKILL.md); 28,786 stars | test actual runtime matrices, include failure cases, record controlled variables, and do not stop at smoke success | live remote probes and product-specific OpenAI API behavior |

Repository popularity metadata was queried from the GitHub repository API on 2026-08-20:
`openai/plugins` 5,121 stars; `agno-agi/agentos-railway` 31;
`openai/openai-agents-python` 28,786; `mode-io/skill-manager` 115; and
`openai/skills` 25,050. Star counts are time-varying discovery context, not evidence of
safety or suitability.
