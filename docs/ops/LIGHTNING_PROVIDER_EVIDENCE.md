# Lightning AI provider evidence

Research date: 2026-07-18. Sources below are official Lightning AI pages (and the
official Lightning SDK project on PyPI). This is documentation evidence only; no
Lightning account or resource was accessed.

| Claim | Official evidence |
|---|---|
| Free plan is US$0 and no credit card is required | [Lightning pricing](https://lightning.ai/pricing/) and [getting started](https://lightning.ai/docs/platform/overview/getting-started) |
| 15 free credits are issued monthly | [Account creation](https://lightning.ai/docs/platform/overview/faq/create-account) and [pricing](https://lightning.ai/pricing/) |
| Credits can be used for GPUs | [Billing and credits](https://lightning.ai/docs/overview/faq/billing) |
| One Lightning credit equals US$1 | [Billing: value conversion](https://lightning.ai/docs/overview/faq/billing) |
| Free credits expire monthly | [Account creation](https://lightning.ai/docs/platform/overview/faq/create-account) |
| Phone verification is required; non-virtual numbers are required | [Account FAQ](https://lightning.ai/docs/platform/overview/faq) |
| Studios retain files and installed environments when hardware changes or sleeps | [AI Studio](https://api.lightning.ai/docs/overview/ai-studio) and [environment persistence](https://lightning.ai/docs/platform/build/ai-studio/environment-persistence) |
| Free storage is available | [Billing and storage](https://lightning.ai/docs/overview/faq/billing) |
| CLI and SDK APIs manage Studios and Jobs, including logs/status | [CLI](https://lightning.ai/docs/overview/cli), [Studio SDK](https://lightning.ai/docs/overview/sdk/studio), [batch jobs SDK](https://lightning.ai/docs/overview/batch-jobs/sdk) |
| On-demand GPU availability is not guaranteed | [GPU marketplace](https://lightning.ai/docs/overview/gpu-marketplace) |
| Free cannot use a custom launch image as the initial Studio image | [Custom Docker images](https://lightning.ai/docs/platform/build/ai-studio/custom-docker-images): custom launch images are described as an Enterprise capability |
| Docker can be built inside a Studio | [Custom Docker images](https://lightning.ai/docs/platform/build/ai-studio/custom-docker-images) |

The official SDK package is pinned separately in
`infrastructure/lightning/requirements-lightning.txt`. The SDK gate inspects the
real `Studio`, `Job`, `Machine`, upload/download, logs/status and stop APIs in
memory while blocking network transports. It does not claim that Jobs execute this
repository's Dockerfile, that CUDA works, that a GPU is available, that preparation
takes under 15 minutes, or that upload/download/recovery has been tested.
