from .base import ReviewContext, ReviewRule
from .bad_practices import (
    BroadExceptRule,
    EvalExecRule,
    HardcodedSecretRule,
    MutableDefaultArgsRule,
    PrintAsLoggingRule,
    ShellTrueRule,
    SqlInterpolationRule,
    SwallowedExceptionRule,
    UnsafePickleRule,
)
from .edge_cases import (
    ConcurrencyLockRule,
    DataShapeValidationRule,
    ExternalCallTimeoutRule,
    FloatEqualityRule,
    IdempotencyRetryRule,
    LargeInputRule,
    NullHandlingRule,
    UnicodeEncodingRule,
    UnboundedRetriesRule,
)
from .logical_flaws import (
    ContradictoryRequirementsRule,
    EmptyInputSemanticsRule,
    OffByOneBoundaryRule,
    TimezoneNaiveDateTimeRule,
    UndefinedTermsRule,
    UnverifiableCriteriaRule,
)
from .testability import (
    GoldenExpectationRule,
    HiddenEnvironmentDepsRule,
    MissingExampleInputsRule,
    VagueAcceptanceVerbsRule,
)

ALL_RULES: tuple[ReviewRule, ...] = (
    # --- logical flaws: clarity & correctness of the spec -------------------
    UndefinedTermsRule(),
    ContradictoryRequirementsRule(),
    UnverifiableCriteriaRule(),
    OffByOneBoundaryRule(),
    EmptyInputSemanticsRule(),
    TimezoneNaiveDateTimeRule(),
    # --- bad practices & safety in the reference implementation -------------
    EvalExecRule(),
    SqlInterpolationRule(),
    HardcodedSecretRule(),
    BroadExceptRule(),
    SwallowedExceptionRule(),
    MutableDefaultArgsRule(),
    PrintAsLoggingRule(),
    ShellTrueRule(),
    UnsafePickleRule(),
    # --- edge cases -----------------------------------------------------------
    FloatEqualityRule(),
    NullHandlingRule(),
    ConcurrencyLockRule(),
    UnboundedRetriesRule(),
    IdempotencyRetryRule(),
    LargeInputRule(),
    UnicodeEncodingRule(),
    ExternalCallTimeoutRule(),
    DataShapeValidationRule(),
    # --- testability ------------------------------------------------------------
    MissingExampleInputsRule(),
    GoldenExpectationRule(),
    VagueAcceptanceVerbsRule(),
    HiddenEnvironmentDepsRule(),
)

__all__ = ["ALL_RULES", "ReviewContext", "ReviewRule"]