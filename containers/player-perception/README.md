# Player perception runtime

Provider-neutral CPU/CUDA-capable contract. Mount the repository and external assets
at `/workspace`, inputs at `/input`, weights at `/models`, and outputs at `/output`.
The image never downloads weights during build. OpenMMLab extras are installed in a
separate controlled image revision when selected; this preparation image is only a
syntax and mount contract.
