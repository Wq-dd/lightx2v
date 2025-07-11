import os
import torch
from lightx2v.models.networks.wan.model import WanModel
from lightx2v.models.networks.wan.weights.pre_weights import WanPreWeights
from lightx2v.models.networks.wan.weights.post_weights import WanPostWeights
from lightx2v.models.networks.wan.weights.transformer_weights import (
    WanTransformerWeights,
)
from lightx2v.models.networks.wan.infer.pre_infer import WanPreInfer
from lightx2v.models.networks.wan.infer.post_infer import WanPostInfer
from lightx2v.models.networks.wan.infer.causvid.transformer_infer import (
    WanTransformerInferCausVid,
)
from lightx2v.utils.envs import *


class WanCausVidModel(WanModel):
    pre_weight_class = WanPreWeights
    post_weight_class = WanPostWeights
    transformer_weight_class = WanTransformerWeights

    def __init__(self, model_path, config, device):
        super().__init__(model_path, config, device)

    def _init_infer_class(self):
        self.pre_infer_class = WanPreInfer
        self.post_infer_class = WanPostInfer
        self.transformer_infer_class = WanTransformerInferCausVid

    def _load_ckpt(self, use_bf16, skip_bf16):
        use_bfloat16 = GET_DTYPE() == "BF16"
        ckpt_path = os.path.join(self.model_path, "causal_model.pt")
        if not os.path.exists(ckpt_path):
            return super()._load_ckpt(use_bf16, skip_bf16)

        weight_dict = torch.load(ckpt_path, map_location="cpu", weights_only=True)

        dtype = torch.bfloat16 if use_bfloat16 else None
        for key, value in weight_dict.items():
            weight_dict[key] = value.to(device=self.device, dtype=dtype)

        return weight_dict

    @torch.no_grad()
    def infer(self, inputs, kv_start, kv_end):
        if self.config["cpu_offload"]:
            self.pre_weight.to_cuda()
            self.post_weight.to_cuda()

        embed, grid_sizes, pre_infer_out = self.pre_infer.infer(self.pre_weight, inputs, positive=True, kv_start=kv_start, kv_end=kv_end)

        x = self.transformer_infer.infer(self.transformer_weights, grid_sizes, embed, *pre_infer_out, kv_start, kv_end)
        self.scheduler.noise_pred = self.post_infer.infer(self.post_weight, x, embed, grid_sizes)[0]

        if self.config["cpu_offload"]:
            self.pre_weight.to_cpu()
            self.post_weight.to_cpu()
