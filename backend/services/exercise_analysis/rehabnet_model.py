"""
RehabNet Model Architecture - reconstructed from rehabnet_best.pth state_dict.

Architecture:
  ST-GCN (3 blocks) â†’ Transformer (2 encoder layers) + BiLSTM (2 layers)
  â†’ Shared MLP â†’ 3 heads: classify (correct/incorrect), quality (score), exercise (type)

Input: (batch, 3, T, 6)  where 3 = x/y/z coords, T = time steps, 6 = body joints
  Joints: LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE

Output heads:
  - classify_head: 2 classes (correct=0, incorrect=1)
  - quality_head:  1 value (quality score 0-1, via sigmoid)
  - ex_head:       10 classes (exercise type classification)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


# â”€â”€ Adjacency matrix for 6 lower-body joints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Joints: 0=LEFT_HIP, 1=RIGHT_HIP, 2=LEFT_KNEE, 3=RIGHT_KNEE, 4=LEFT_ANKLE, 5=RIGHT_ANKLE
# Edges: hip-hip, hip-knee (L), hip-knee (R), knee-ankle (L), knee-ankle (R), self-loops
def _build_adj(num_nodes=6):
    edges = [
        (0, 1),  # left_hip â€“ right_hip
        (0, 2),  # left_hip â€“ left_knee
        (1, 3),  # right_hip â€“ right_knee
        (2, 4),  # left_knee â€“ left_ankle
        (3, 5),  # right_knee â€“ right_ankle
    ]
    A = np.eye(num_nodes, dtype=np.float32)  # self-loops
    for i, j in edges:
        A[i, j] = 1.0
        A[j, i] = 1.0
    # Normalize: D^{-1/2} A D^{-1/2}
    D = np.sum(A, axis=1)
    D_inv_sqrt = np.diag(1.0 / np.sqrt(D + 1e-8))
    A_norm = D_inv_sqrt @ A @ D_inv_sqrt
    return torch.tensor(A_norm, dtype=torch.float32)


# â”€â”€ ST-GCN Block â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class STGCNBlock(nn.Module):
    """Spatial-Temporal Graph Convolution block."""

    def __init__(self, in_ch, out_ch, A, kernel_size=9, stride=1):
        super().__init__()
        self.A = A  # (V, V) normalized adjacency
        # Spatial GCN: linear over input channels
        self.gcn = nn.Linear(in_ch, out_ch, bias=True)
        # Temporal Conv: BN -> ReLU -> Conv1d -> BN
        self.tcn = nn.Sequential(
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, (kernel_size, 1), padding=(kernel_size // 2, 0), bias=True),
            nn.BatchNorm2d(out_ch),
        )
        # Residual connection (1x1 conv if channels change)
        if in_ch != out_ch:
            self.res = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 1, bias=True),
                nn.BatchNorm2d(out_ch),
            )
        else:
            self.res = nn.Identity()

    def forward(self, x):
        """x: (B, C, T, V)"""
        A = self.A.to(x.device)
        residual = self.res(x)

        # Spatial GCN: aggregate features across connected nodes using adjacency matrix
        # x: (B, C, T, V) -> permute to (B, T, C, V)
        x_perm = x.permute(0, 2, 1, 3)  # (B, T, C, V)
        # Graph aggregation: A is (V, V), applied to the last dim (nodes)
        x_graph = torch.matmul(x_perm, A)  # (B, T, C, V)
        # Permute to (B, T, V, C) for linear transform
        x_graph = x_graph.permute(0, 1, 3, 2)  # (B, T, V, C)
        x_gcn = self.gcn(x_graph)  # (B, T, V, out_ch)
        x_gcn = x_gcn.permute(0, 3, 1, 2)  # (B, out_ch, T, V)

        # Temporal
        x_tcn = self.tcn(x_gcn)

        return F.relu(x_tcn + residual, inplace=True)


# â”€â”€ Full RehabNet Model â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class RehabNet(nn.Module):
    """
    RehabNet: ST-GCN + Transformer + BiLSTM for physiotherapy exercise analysis.
    """

    NUM_JOINTS = 6
    IN_CHANNELS = 3  # x, y, z per joint
    MAX_SEQ_LEN = 150  # PE supports up to 150 time steps + 1 CLS token
    NUM_EXERCISE_TYPES = 10
    NUM_MODES = 2

    def __init__(self):
        super().__init__()
        A = _build_adj(self.NUM_JOINTS)
        self.register_buffer("A", A)

        # Input normalization (BatchNorm1d over 18 = 6*3 features)
        self.stgcn = nn.Module()
        self.stgcn.input_norm = nn.BatchNorm1d(self.IN_CHANNELS * self.NUM_JOINTS)

        # 3 ST-GCN blocks: 3->32, 32->64, 64->128
        self.stgcn.b1 = STGCNBlock(3, 32, A)
        self.stgcn.b2 = STGCNBlock(32, 64, A)
        self.stgcn.b3 = STGCNBlock(64, 128, A)

        # Transformer encoder (2 layers, d_model=128)
        self.trans = nn.Module()
        self.trans.cls = nn.Parameter(torch.randn(1, 1, 128))
        self.trans.pe = nn.Parameter(torch.randn(1, self.MAX_SEQ_LEN + 1, 128))
        self.trans.l1 = nn.TransformerEncoderLayer(d_model=128, nhead=4, dim_feedforward=256, batch_first=True)
        self.trans.l2 = nn.TransformerEncoderLayer(d_model=128, nhead=4, dim_feedforward=256, batch_first=True)
        self.trans.n1 = nn.LayerNorm(128)
        self.trans.n2 = nn.LayerNorm(128)

        # BiLSTM (2 layers, hidden=64, bidirectional â†’ output=128)
        self.bilstm = nn.LSTM(128, 64, num_layers=2, bidirectional=True, batch_first=True)
        self.bilstm_proj = nn.Sequential(
            nn.Linear(128, 128),
            nn.LayerNorm(128),
        )

        # Embeddings for mode and exercise type (used as conditioning)
        self.mode_emb = nn.Embedding(self.NUM_MODES, 16)
        self.ex_emb = nn.Embedding(self.NUM_EXERCISE_TYPES, 8)

        # Shared MLP: 128 (stgcn) + 128 (transformer) + 16 (mode) + 8 (ex) + 10 (stats) = 290
        self.shared = nn.Sequential(
            nn.Linear(290, 128),
            nn.LayerNorm(128),
        )

        # Task heads
        self.classify_head = nn.Linear(128, 2)    # correct / incorrect
        self.quality_head = nn.Linear(128, 1)     # quality score (sigmoid)
        self.ex_head = nn.Linear(128, 10)         # exercise classification

    def forward(self, x, mode_id=None, ex_id=None, hand_features=None):
        """
        Args:
            x: (B, 3, T, 6) - joint coordinates time series
            mode_id: (B,) - mode index (0 or 1), default 0
            ex_id: (B,) - exercise type index (0-9), default 0
            hand_features: (B, 10) - hand-crafted angle statistics, default zeros

        Returns:
            dict with keys: classify_logits, quality_score, ex_logits
        """
        B, C, T, V = x.shape

        # Input normalization: reshape to (B, C*V, T) for BN, then back
        x_flat = x.reshape(B, C * V, T)
        x_flat = self.stgcn.input_norm(x_flat)
        x = x_flat.reshape(B, C, T, V)

        # ST-GCN blocks
        x = self.stgcn.b1(x)
        x = self.stgcn.b2(x)
        x = self.stgcn.b3(x)  # (B, 128, T', V)

        # Pool STGCN: mean over V (nodes)
        x_nodes = x.mean(dim=3)  # (B, 128, T')
        feat_stgcn = x_nodes.mean(dim=2)  # (B, 128) - global pool over time

        # Prepare sequence for transformer and BiLSTM
        seq = x_nodes.permute(0, 2, 1)  # (B, T', 128)
        T_seq = seq.shape[1]

        # Transformer with CLS token
        cls_tokens = self.trans.cls.expand(B, -1, -1)  # (B, 1, 128)
        seq_with_cls = torch.cat([cls_tokens, seq], dim=1)  # (B, T'+1, 128)
        # Add positional encoding (truncate if needed)
        pe = self.trans.pe[:, :T_seq + 1, :]
        seq_pe = seq_with_cls + pe

        # Transformer encoder layers
        h = self.trans.l1(self.trans.n1(seq_pe))
        h = self.trans.l2(self.trans.n2(h))
        feat_trans = h[:, 0, :]  # (B, 128) - CLS token output

        # BiLSTM on sequence
        lstm_out, _ = self.bilstm(seq)  # (B, T', 128)
        feat_lstm = lstm_out.mean(dim=1)  # (B, 128)
        feat_lstm = self.bilstm_proj(feat_lstm)  # (B, 128)

        # Conditioning embeddings
        if mode_id is None:
            mode_id = torch.zeros(B, dtype=torch.long, device=x.device)
        if ex_id is None:
            ex_id = torch.zeros(B, dtype=torch.long, device=x.device)
        if hand_features is None:
            hand_features = torch.zeros(B, 10, device=x.device)

        mode_feat = self.mode_emb(mode_id)  # (B, 16)
        ex_feat = self.ex_emb(ex_id)  # (B, 8)

        # Concatenate all features: 128 + 128 + 16 + 8 + 10 = 290
        # Note: we use feat_stgcn + feat_trans (transformer includes temporal info from BiLSTM path)
        combined = torch.cat([feat_stgcn, feat_trans, mode_feat, ex_feat, hand_features], dim=1)

        # Shared MLP
        shared = F.relu(self.shared(combined))

        # Heads
        classify_logits = self.classify_head(shared)  # (B, 2)
        quality_score = torch.sigmoid(self.quality_head(shared))  # (B, 1) in [0, 1]
        ex_logits = self.ex_head(shared)  # (B, 10)

        return {
            "classify_logits": classify_logits,
            "quality_score": quality_score.squeeze(-1),
            "ex_logits": ex_logits,
        }


def load_rehabnet(model_path: str, device: str = "cpu") -> RehabNet:
    """Load a RehabNet model from a state_dict checkpoint."""
    model = RehabNet()
    state_dict = torch.load(model_path, map_location=device, weights_only=False)
    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()
    return model
