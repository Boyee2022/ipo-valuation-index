"""``valnet``：Valuation Computation Graph（VCG）最小可运行原型。

纯标准库、无第三方依赖、无网络/LLM 调用；只用于验证"类型化模块 + DAG 执行器 +
门控/残差/池化 + trace"的接口形状，**不接入生产代码**。

快速开始（在 ``prototype/`` 目录下）::

    python3 -m unittest discover -s valnet/tests -v
    python3 -m valnet.runner
"""

from .spec import (
    MODULE_KINDS,
    POOL_KINDS,
    Batch,
    EdgeSpec,
    GraphSpec,
    Interval,
    MaskMap,
    ModuleKind,
    ModuleOutput,
    ModuleSpec,
    NodeSpec,
    PoolKind,
    PoolSpec,
    Scalar,
)
from .pooling import (
    PoolingError,
    linear_pool,
    log_pool,
    pool_confidence,
    pool_intervals,
    pool_values,
    product_pool,
)
from .graph import (
    RESIDUAL_CLIP,
    STATUS_FAILED,
    STATUS_GATED,
    STATUS_OK,
    CycleError,
    DuplicateNodeError,
    ExecutionTrace,
    GraphError,
    GraphResult,
    GraphValidationError,
    MissingDependencyError,
    TraceEntry,
    bounded_residual,
    execute,
    topological_order,
    validate_graph,
)
from .modules import (
    ALL_MODULES,
    COMPARABLE,
    DCF,
    INDUSTRY_BASELINE,
    SENTIMENT,
)

__version__ = "0.1.0"

__all__ = [
    # spec
    "Batch",
    "EdgeSpec",
    "GraphSpec",
    "Interval",
    "MaskMap",
    "ModuleKind",
    "ModuleOutput",
    "ModuleSpec",
    "NodeSpec",
    "PoolKind",
    "PoolSpec",
    "Scalar",
    "MODULE_KINDS",
    "POOL_KINDS",
    # pooling
    "PoolingError",
    "linear_pool",
    "log_pool",
    "pool_confidence",
    "pool_intervals",
    "pool_values",
    "product_pool",
    # graph
    "CycleError",
    "DuplicateNodeError",
    "ExecutionTrace",
    "GraphError",
    "GraphResult",
    "GraphValidationError",
    "MissingDependencyError",
    "RESIDUAL_CLIP",
    "STATUS_FAILED",
    "STATUS_GATED",
    "STATUS_OK",
    "TraceEntry",
    "bounded_residual",
    "execute",
    "topological_order",
    "validate_graph",
    # modules
    "ALL_MODULES",
    "COMPARABLE",
    "DCF",
    "INDUSTRY_BASELINE",
    "SENTIMENT",
    # package
    "__version__",
]
