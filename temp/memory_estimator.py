#!/usr/bin/env python3
"""
Memory Estimator for llama.cpp / llama.rn models

This module provides functions to estimate memory requirements for LLM inference
based on GGUF metadata and user-provided runtime parameters.

Usage:
    from memory_estimator import estimate_memory

    # Model info from GGUF metadata
    model_info = {
        'file_size': 1_500_000_000,  # bytes
        'architecture': 'llama',
        'n_layers': 32,
        'n_embd': 4096,
        'n_head': 32,
        'n_head_kv': 8,  # For GQA models
        'n_vocab': 128256,
        # Optional for SWA models (Gemma 2/3):
        'sliding_window': 4096,
        'swa_pattern': [True, False, True, False, ...],  # or None
        # Optional for hybrid models (LFM):
        'n_head_kv_per_layer': [0, 0, 8, 0, ...],  # or None
    }

    # User-provided runtime parameters
    runtime_params = {
        'n_ctx': 4096,
        'n_ubatch': 512,
        'type_k': 'f16',
        'type_v': 'f16',
    }

    result = estimate_memory(model_info, runtime_params)
    print(f"Total estimated memory: {result['total'] / 1e9:.2f} GB")
"""

import json
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# CONSTANTS
# =============================================================================

# Bytes per element for different data types
# Based on ggml quantization block sizes
DTYPE_BYTES = {
    'f32': 4.0,
    'f16': 2.0,
    'bf16': 2.0,
    'q8_0': 34 / 32,   # 32 values + 2 byte scale = 34 bytes for 32 elements
    'q4_0': 18 / 32,   # 32 values + 2 byte scale = 18 bytes for 32 elements
    'q4_1': 20 / 32,
    'q5_0': 22 / 32,
    'q5_1': 24 / 32,
    'q4_k': 144 / 256,
    'q5_k': 176 / 256,
    'q6_k': 210 / 256,
    'iq4_nl': 18 / 32,
    'iq3_m': 0.40625,  # ~13/32
    'iq2_m': 0.3125,   # ~10/32
    'iq1_m': 0.21875,  # ~7/32
}

# Default vocab sizes by architecture (when not in GGUF metadata)
ARCH_DEFAULT_VOCAB = {
    'llama': 128256,
    'gemma2': 256000,
    'gemma3n': 262144,
    'qwen2': 151936,
    'qwen3': 151936,
    'lfm2': 65536,
    'phi3': 32064,
    'mistral': 32000,
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ModelInfo:
    """Model architecture information from GGUF metadata."""
    file_size: int
    architecture: str
    n_layers: int
    n_embd: int
    n_head: int
    n_head_kv: int
    n_vocab: int
    n_embd_head_k: Optional[int] = None
    n_embd_head_v: Optional[int] = None
    # SWA (Sliding Window Attention) - Gemma 2/3
    sliding_window: Optional[int] = None
    swa_pattern: Optional[list[bool]] = None
    # Hybrid models (Mamba + Attention) - LFM
    n_head_kv_per_layer: Optional[list[int]] = None

    def __post_init__(self):
        # Derive head dimensions if not provided
        if self.n_embd_head_k is None:
            self.n_embd_head_k = self.n_embd // self.n_head
        if self.n_embd_head_v is None:
            self.n_embd_head_v = self.n_embd // self.n_head

    @property
    def is_hybrid(self) -> bool:
        """Check if model is hybrid (has layers without KV cache)."""
        if self.n_head_kv_per_layer is not None:
            return any(x == 0 for x in self.n_head_kv_per_layer)
        return False

    @property
    def has_swa(self) -> bool:
        """Check if model uses Sliding Window Attention."""
        return self.sliding_window is not None or self.swa_pattern is not None

    @property
    def n_attention_layers(self) -> int:
        """Number of layers with KV cache (for hybrid models)."""
        if self.n_head_kv_per_layer is not None:
            return sum(1 for x in self.n_head_kv_per_layer if x > 0)
        return self.n_layers


@dataclass
class RuntimeParams:
    """User-provided runtime parameters."""
    n_ctx: int
    n_ubatch: int = 512
    type_k: str = 'f16'
    type_v: str = 'f16'


@dataclass
class MemoryEstimate:
    """Memory estimation result."""
    weights: int
    kv_cache: int
    compute_buffer: int
    output_buffer: int

    @property
    def total(self) -> int:
        return self.weights + self.kv_cache + self.compute_buffer + self.output_buffer

    def to_dict(self) -> dict:
        return {
            'weights': self.weights,
            'kv_cache': self.kv_cache,
            'compute_buffer': self.compute_buffer,
            'output_buffer': self.output_buffer,
            'total': self.total,
        }

    def summary(self) -> str:
        """Return human-readable summary."""
        def fmt(b: int) -> str:
            if b >= 1e9:
                return f"{b / 1e9:.2f} GB"
            elif b >= 1e6:
                return f"{b / 1e6:.1f} MB"
            else:
                return f"{b / 1e3:.1f} KB"

        total = self.total
        return (
            f"Memory Estimate:\n"
            f"  Weights:        {fmt(self.weights):>10} ({self.weights / total * 100:.1f}%)\n"
            f"  KV Cache:       {fmt(self.kv_cache):>10} ({self.kv_cache / total * 100:.1f}%)\n"
            f"  Compute Buffer: {fmt(self.compute_buffer):>10} ({self.compute_buffer / total * 100:.1f}%)\n"
            f"  Output Buffer:  {fmt(self.output_buffer):>10} ({self.output_buffer / total * 100:.1f}%)\n"
            f"  ─────────────────────────────\n"
            f"  Total:          {fmt(total):>10}"
        )


# =============================================================================
# CORE CALCULATION FUNCTIONS
# =============================================================================

def bytes_per_element(dtype: str) -> float:
    """Get bytes per element for a data type."""
    return DTYPE_BYTES.get(dtype.lower(), 2.0)  # Default to f16


def calculate_kv_cache(model: ModelInfo, params: RuntimeParams) -> int:
    """
    Calculate KV cache memory.

    Formula:
        Standard:  n_layers × n_ctx × (n_embd_head_k + n_embd_head_v) × n_head_kv × bytes
        Hybrid:    Only attention layers have KV cache
        SWA:       SWA layers use min(n_ctx, sliding_window), non-SWA use full context
    """
    bytes_k = bytes_per_element(params.type_k)
    bytes_v = bytes_per_element(params.type_v)
    n_ctx = params.n_ctx

    # Per-cell memory (K + V for one position, one layer)
    cell_k = model.n_embd_head_k * model.n_head_kv * bytes_k
    cell_v = model.n_embd_head_v * model.n_head_kv * bytes_v
    cell_kv = cell_k + cell_v

    # SWA models: separate calculation for SWA and non-SWA layers
    if model.has_swa:
        if model.swa_pattern is not None:
            # Explicit pattern (Gemma 3n style)
            swa_layers = sum(1 for x in model.swa_pattern if x)
            non_swa_layers = sum(1 for x in model.swa_pattern if not x)
        else:
            # Alternating pattern (Gemma 2 style)
            swa_layers = model.n_layers // 2
            non_swa_layers = model.n_layers - swa_layers

        swa_cells = min(n_ctx, model.sliding_window) if model.sliding_window else n_ctx
        non_swa_cells = n_ctx

        return int(swa_layers * swa_cells * cell_kv + non_swa_layers * non_swa_cells * cell_kv)

    # Hybrid models: per-layer KV heads
    if model.is_hybrid and model.n_head_kv_per_layer is not None:
        total = 0
        for layer_kv_heads in model.n_head_kv_per_layer:
            if layer_kv_heads > 0:
                layer_cell_k = model.n_embd_head_k * layer_kv_heads * bytes_k
                layer_cell_v = model.n_embd_head_v * layer_kv_heads * bytes_v
                total += n_ctx * (layer_cell_k + layer_cell_v)
        return int(total)

    # Standard model
    n_layers = model.n_attention_layers if model.is_hybrid else model.n_layers
    return int(n_layers * n_ctx * cell_kv)


def calculate_compute_buffer(model: ModelInfo, params: RuntimeParams) -> int:
    """
    Calculate compute buffer memory.

    Formula: (n_vocab + n_embd) × n_ubatch × 4

    The compute buffer holds:
    1. Output logits tensor: [n_vocab, n_ubatch] in f32
    2. One hidden state buffer: [n_embd, n_ubatch] in f32

    For hybrid models (Mamba+Attention): add ~15% overhead for SSM state buffers.
    """
    base = (model.n_vocab + model.n_embd) * params.n_ubatch * 4

    if model.is_hybrid:
        return int(base * 1.15)

    return int(base)


def calculate_output_buffer(model: ModelInfo) -> int:
    """
    Calculate output buffer memory.

    Formula: n_vocab × 4 bytes (f32 logits)
    """
    return model.n_vocab * 4


# =============================================================================
# MAIN API
# =============================================================================

def estimate_memory(model_info: dict, runtime_params: dict) -> MemoryEstimate:
    """
    Estimate total memory requirements for model inference.

    Args:
        model_info: Dictionary with model architecture info:
            - file_size: Model file size in bytes
            - architecture: Model architecture (e.g., 'llama', 'qwen2')
            - n_layers: Number of transformer layers
            - n_embd: Embedding dimension
            - n_head: Number of attention heads
            - n_head_kv: Number of KV heads (for GQA)
            - n_vocab: Vocabulary size
            - n_embd_head_k: (optional) Key head dimension
            - n_embd_head_v: (optional) Value head dimension
            - sliding_window: (optional) SWA window size
            - swa_pattern: (optional) List of bools for SWA layers
            - n_head_kv_per_layer: (optional) List of KV heads per layer

        runtime_params: Dictionary with runtime parameters:
            - n_ctx: Context size
            - n_ubatch: Micro-batch size (default: 512)
            - type_k: KV cache key type (default: 'f16')
            - type_v: KV cache value type (default: 'f16')

    Returns:
        MemoryEstimate with weights, kv_cache, compute_buffer, output_buffer, total
    """
    model = ModelInfo(
        file_size=model_info['file_size'],
        architecture=model_info.get('architecture', 'llama'),
        n_layers=model_info['n_layers'],
        n_embd=model_info['n_embd'],
        n_head=model_info['n_head'],
        n_head_kv=model_info.get('n_head_kv', model_info['n_head']),
        n_vocab=model_info.get('n_vocab', ARCH_DEFAULT_VOCAB.get(
            model_info.get('architecture', 'llama'), 128000
        )),
        n_embd_head_k=model_info.get('n_embd_head_k'),
        n_embd_head_v=model_info.get('n_embd_head_v'),
        sliding_window=model_info.get('sliding_window'),
        swa_pattern=model_info.get('swa_pattern'),
        n_head_kv_per_layer=model_info.get('n_head_kv_per_layer'),
    )

    params = RuntimeParams(
        n_ctx=runtime_params['n_ctx'],
        n_ubatch=runtime_params.get('n_ubatch', 512),
        type_k=runtime_params.get('type_k', 'f16'),
        type_v=runtime_params.get('type_v', 'f16'),
    )

    return MemoryEstimate(
        weights=model.file_size,
        kv_cache=calculate_kv_cache(model, params),
        compute_buffer=calculate_compute_buffer(model, params),
        output_buffer=calculate_output_buffer(model),
    )


def estimate_from_gguf_info(gguf_info: dict, file_size: int, runtime_params: dict) -> MemoryEstimate:
    """
    Estimate memory from raw GGUF metadata.

    This is a convenience function that parses GGUF metadata format directly.

    Args:
        gguf_info: Raw GGUF metadata dictionary (e.g., from llama.rn)
        file_size: Model file size in bytes
        runtime_params: Runtime parameters (n_ctx, n_ubatch, type_k, type_v)

    Returns:
        MemoryEstimate
    """
    arch = gguf_info.get('general.architecture', 'llama')

    def get_arch_value(field: str, default=None):
        """Get architecture-specific value from GGUF metadata."""
        key = f"{arch}.{field}"
        value = gguf_info.get(key)
        if value is not None:
            if isinstance(value, str):
                try:
                    if '.' in value:
                        return float(value)
                    return int(value)
                except ValueError:
                    return value
            return value
        return default

    # Parse core parameters
    n_layers = get_arch_value('block_count')
    n_embd = get_arch_value('embedding_length')
    n_head = get_arch_value('attention.head_count')
    n_head_kv = get_arch_value('attention.head_count_kv', n_head)
    n_vocab = get_arch_value('vocab_size')

    # Head dimensions
    n_embd_head_k = get_arch_value('attention.key_length')
    n_embd_head_v = get_arch_value('attention.value_length')

    # SWA parameters
    sliding_window = get_arch_value('attention.sliding_window')
    swa_pattern_str = get_arch_value('attention.sliding_window_pattern')
    swa_pattern = None
    if swa_pattern_str and isinstance(swa_pattern_str, str):
        try:
            swa_pattern = json.loads(swa_pattern_str)
        except json.JSONDecodeError:
            pass

    # Hybrid model detection (per-layer KV heads)
    n_head_kv_per_layer = None
    head_kv_str = get_arch_value('attention.head_count_kv')
    if isinstance(head_kv_str, str) and head_kv_str.startswith('['):
        try:
            n_head_kv_per_layer = json.loads(head_kv_str)
            # Get n_head_kv from first non-zero value
            non_zero = [x for x in n_head_kv_per_layer if x > 0]
            if non_zero:
                n_head_kv = non_zero[0]
        except json.JSONDecodeError:
            pass

    model_info = {
        'file_size': file_size,
        'architecture': arch,
        'n_layers': n_layers,
        'n_embd': n_embd,
        'n_head': n_head,
        'n_head_kv': n_head_kv,
        'n_vocab': n_vocab or ARCH_DEFAULT_VOCAB.get(arch, 128000),
        'n_embd_head_k': n_embd_head_k,
        'n_embd_head_v': n_embd_head_v,
        'sliding_window': sliding_window,
        'swa_pattern': swa_pattern,
        'n_head_kv_per_layer': n_head_kv_per_layer,
    }

    return estimate_memory(model_info, runtime_params)


# =============================================================================
# CLI EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Example: Llama 3.2 1B
    model = {
        'file_size': 1_321_079_200,
        'architecture': 'llama',
        'n_layers': 16,
        'n_embd': 2048,
        'n_head': 32,
        'n_head_kv': 8,
        'n_vocab': 128256,
        'n_embd_head_k': 64,
        'n_embd_head_v': 64,
    }

    params = {
        'n_ctx': 2048,
        'n_ubatch': 512,
        'type_k': 'f16',
        'type_v': 'f16',
    }

    result = estimate_memory(model, params)
    print("Llama 3.2 1B (Q8_0) @ ctx=2048, kv=f16")
    print(result.summary())
    print()

    # Example with q4_0 KV cache
    params_q4 = {
        'n_ctx': 8192,
        'n_ubatch': 512,
        'type_k': 'q4_0',
        'type_v': 'q4_0',
    }

    result_q4 = estimate_memory(model, params_q4)
    print("Llama 3.2 1B (Q8_0) @ ctx=8192, kv=q4_0")
    print(result_q4.summary())
    print()

    # Example: Gemma 2 with SWA
    gemma2 = {
        'file_size': 2_151_393_120,
        'architecture': 'gemma2',
        'n_layers': 26,
        'n_embd': 2304,
        'n_head': 8,
        'n_head_kv': 4,
        'n_vocab': 256000,
        'n_embd_head_k': 256,
        'n_embd_head_v': 256,
        'sliding_window': 4096,
    }

    result_gemma = estimate_memory(gemma2, params)
    print("Gemma 2 2B (Q6_K) @ ctx=2048, kv=f16 (with SWA)")
    print(result_gemma.summary())
    print()

    # Example: LFM hybrid model
    lfm = {
        'file_size': 695_752_160,
        'architecture': 'lfm2',
        'n_layers': 16,
        'n_embd': 2048,
        'n_head': 32,
        'n_head_kv': 8,
        'n_vocab': 65536,
        'n_embd_head_k': 64,
        'n_embd_head_v': 64,
        'n_head_kv_per_layer': [0, 0, 8, 0, 0, 8, 0, 0, 8, 0, 8, 0, 8, 0, 8, 0],
    }

    result_lfm = estimate_memory(lfm, params)
    print("LFM 2.5 1.2B (Q4_0) @ ctx=2048, kv=f16 (hybrid)")
    print(result_lfm.summary())
